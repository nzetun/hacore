"""Switches for the Elexa Guardian integration."""
from __future__ import annotations

from typing import Any

from aioguardian import Client
from aioguardian.errors import GuardianError
import voluptuous as vol

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FILENAME, CONF_PORT, CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import ValveControllerEntity
from .const import (
    API_VALVE_STATUS,
    CONF_UID,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DATA_PAIRED_SENSOR_MANAGER,
    DOMAIN,
    LOGGER,
)

ATTR_AVG_CURRENT = "average_current"
ATTR_INST_CURRENT = "instantaneous_current"
ATTR_INST_CURRENT_DDT = "instantaneous_current_ddt"
ATTR_TRAVEL_COUNT = "travel_count"

SERVICE_DISABLE_AP = "disable_ap"
SERVICE_ENABLE_AP = "enable_ap"
SERVICE_PAIR_SENSOR = "pair_sensor"
SERVICE_REBOOT = "reboot"
SERVICE_RESET_VALVE_DIAGNOSTICS = "reset_valve_diagnostics"
SERVICE_UNPAIR_SENSOR = "unpair_sensor"
SERVICE_UPGRADE_FIRMWARE = "upgrade_firmware"

SWITCH_KIND_VALVE = "valve"

SWITCH_DESCRIPTION_VALVE = SwitchEntityDescription(
    key=SWITCH_KIND_VALVE,
    name="Valve Controller",
    icon="mdi:water",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Guardian switches based on a config entry."""
    platform = entity_platform.async_get_current_platform()

    for service_name, schema, method in (
        (SERVICE_DISABLE_AP, {}, "async_disable_ap"),
        (SERVICE_ENABLE_AP, {}, "async_enable_ap"),
        (SERVICE_PAIR_SENSOR, {vol.Required(CONF_UID): cv.string}, "async_pair_sensor"),
        (SERVICE_REBOOT, {}, "async_reboot"),
        (SERVICE_RESET_VALVE_DIAGNOSTICS, {}, "async_reset_valve_diagnostics"),
        (
            SERVICE_UPGRADE_FIRMWARE,
            {
                vol.Optional(CONF_URL): cv.url,
                vol.Optional(CONF_PORT): cv.port,
                vol.Optional(CONF_FILENAME): cv.string,
            },
            "async_upgrade_firmware",
        ),
        (
            SERVICE_UNPAIR_SENSOR,
            {vol.Required(CONF_UID): cv.string},
            "async_unpair_sensor",
        ),
    ):
        platform.async_register_entity_service(service_name, schema, method)

    async_add_entities(
        [
            ValveControllerSwitch(
                entry,
                hass.data[DOMAIN][entry.entry_id][DATA_CLIENT],
                hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR],
            )
        ]
    )


class ValveControllerSwitch(ValveControllerEntity, SwitchEntity):
    """Define a switch to open/close the Guardian valve."""

    def __init__(
        self,
        entry: ConfigEntry,
        client: Client,
        coordinators: dict[str, DataUpdateCoordinator],
    ) -> None:
        """Initialize."""
        super().__init__(entry, coordinators, SWITCH_DESCRIPTION_VALVE)

        self._attr_is_on = True
        self._client = client

    async def _async_continue_entity_setup(self) -> None:
        """Register API interest (and related tasks) when the entity is added."""
        self.async_add_coordinator_update_listener(API_VALVE_STATUS)

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Update the entity."""
        self._attr_available = self.coordinators[API_VALVE_STATUS].last_update_success
        self._attr_is_on = self.coordinators[API_VALVE_STATUS].data["state"] in (
            "start_opening",
            "opening",
            "finish_opening",
            "opened",
        )

        self._attr_extra_state_attributes.update(
            {
                ATTR_AVG_CURRENT: self.coordinators[API_VALVE_STATUS].data[
                    "average_current"
                ],
                ATTR_INST_CURRENT: self.coordinators[API_VALVE_STATUS].data[
                    "instantaneous_current"
                ],
                ATTR_INST_CURRENT_DDT: self.coordinators[API_VALVE_STATUS].data[
                    "instantaneous_current_ddt"
                ],
                ATTR_TRAVEL_COUNT: self.coordinators[API_VALVE_STATUS].data[
                    "travel_count"
                ],
            }
        )

    async def async_disable_ap(self) -> None:
        """Disable the device's onboard access point."""
        try:
            async with self._client:
                await self._client.wifi.disable_ap()
        except GuardianError as err:
            LOGGER.error("Error while disabling valve controller AP: %s", err)

    async def async_enable_ap(self) -> None:
        """Enable the device's onboard access point."""
        try:
            async with self._client:
                await self._client.wifi.enable_ap()
        except GuardianError as err:
            LOGGER.error("Error while enabling valve controller AP: %s", err)

    async def async_pair_sensor(self, *, uid: str) -> None:
        """Add a new paired sensor."""
        try:
            async with self._client:
                await self._client.sensor.pair_sensor(uid)
        except GuardianError as err:
            LOGGER.error("Error while adding paired sensor: %s", err)
            return

        await self.hass.data[DOMAIN][self._entry.entry_id][
            DATA_PAIRED_SENSOR_MANAGER
        ].async_pair_sensor(uid)

    async def async_reboot(self) -> None:
        """Reboot the device."""
        try:
            async with self._client:
                await self._client.system.reboot()
        except GuardianError as err:
            LOGGER.error("Error while rebooting valve controller: %s", err)

    async def async_reset_valve_diagnostics(self) -> None:
        """Fully reset system motor diagnostics."""
        try:
            async with self._client:
                await self._client.valve.reset()
        except GuardianError as err:
            LOGGER.error("Error while resetting valve diagnostics: %s", err)

    async def async_unpair_sensor(self, *, uid: str) -> None:
        """Add a new paired sensor."""
        try:
            async with self._client:
                await self._client.sensor.unpair_sensor(uid)
        except GuardianError as err:
            LOGGER.error("Error while removing paired sensor: %s", err)
            return

        await self.hass.data[DOMAIN][self._entry.entry_id][
            DATA_PAIRED_SENSOR_MANAGER
        ].async_unpair_sensor(uid)

    async def async_upgrade_firmware(
        self, *, url: str, port: int, filename: str
    ) -> None:
        """Upgrade the device firmware."""
        try:
            async with self._client:
                await self._client.system.upgrade_firmware(
                    url=url,
                    port=port,
                    filename=filename,
                )
        except GuardianError as err:
            LOGGER.error("Error while upgrading firmware: %s", err)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the valve off (closed)."""
        try:
            async with self._client:
                await self._client.valve.close()
        except GuardianError as err:
            LOGGER.error("Error while closing the valve: %s", err)
            return

        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the valve on (open)."""
        try:
            async with self._client:
                await self._client.valve.open()
        except GuardianError as err:
            LOGGER.error("Error while opening the valve: %s", err)
            return

        self._attr_is_on = True
        self.async_write_ha_state()
