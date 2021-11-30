"""The Synology DSM component."""
from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any

import async_timeout
from synology_dsm import SynologyDSM
from synology_dsm.api.core.security import SynoCoreSecurity
from synology_dsm.api.core.system import SynoCoreSystem
from synology_dsm.api.core.upgrade import SynoCoreUpgrade
from synology_dsm.api.core.utilization import SynoCoreUtilization
from synology_dsm.api.dsm.information import SynoDSMInformation
from synology_dsm.api.dsm.network import SynoDSMNetwork
from synology_dsm.api.storage.storage import SynoStorage
from synology_dsm.api.surveillance_station import SynoSurveillanceStation
from synology_dsm.api.surveillance_station.camera import SynoCamera
from synology_dsm.exceptions import (
    SynologyDSMAPIErrorException,
    SynologyDSMLogin2SARequiredException,
    SynologyDSMLoginDisabledAccountException,
    SynologyDSMLoginFailedException,
    SynologyDSMLoginInvalidException,
    SynologyDSMLoginPermissionDeniedException,
    SynologyDSMRequestException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import (
    DeviceEntry,
    async_get_registry as get_dev_reg,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_DEVICE_TOKEN,
    CONF_SERIAL,
    COORDINATOR_CAMERAS,
    COORDINATOR_CENTRAL,
    COORDINATOR_SWITCHES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    EXCEPTION_DETAILS,
    EXCEPTION_UNKNOWN,
    PLATFORMS,
    SERVICE_REBOOT,
    SERVICE_SHUTDOWN,
    SERVICES,
    SYNO_API,
    SYSTEM_LOADED,
    UNDO_UPDATE_LISTENER,
    SynologyDSMEntityDescription,
)

CONFIG_SCHEMA = cv.deprecated(DOMAIN)


ATTRIBUTION = "Data provided by Synology"


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Synology DSM sensors."""

    # Migrate device indentifiers
    dev_reg = await get_dev_reg(hass)
    devices: list[DeviceEntry] = device_registry.async_entries_for_config_entry(
        dev_reg, entry.entry_id
    )
    for device in devices:
        old_identifier = list(next(iter(device.identifiers)))
        if len(old_identifier) > 2:
            new_identifier = {
                (old_identifier.pop(0), "_".join([str(x) for x in old_identifier]))
            }
            _LOGGER.debug(
                "migrate identifier '%s' to '%s'", device.identifiers, new_identifier
            )
            dev_reg.async_update_device(device.id, new_identifiers=new_identifier)

    # Migrate existing entry configuration
    if entry.data.get(CONF_VERIFY_SSL) is None:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL}
        )

    # Continue setup
    api = SynoApi(hass, entry)
    try:
        await api.async_setup()
    except (
        SynologyDSMLogin2SARequiredException,
        SynologyDSMLoginDisabledAccountException,
        SynologyDSMLoginInvalidException,
        SynologyDSMLoginPermissionDeniedException,
    ) as err:
        if err.args[0] and isinstance(err.args[0], dict):
            # pylint: disable=no-member
            details = err.args[0].get(EXCEPTION_DETAILS, EXCEPTION_UNKNOWN)
        else:
            details = EXCEPTION_UNKNOWN
        raise ConfigEntryAuthFailed(f"reason: {details}") from err
    except (SynologyDSMLoginFailedException, SynologyDSMRequestException) as err:
        if err.args[0] and isinstance(err.args[0], dict):
            # pylint: disable=no-member
            details = err.args[0].get(EXCEPTION_DETAILS, EXCEPTION_UNKNOWN)
        else:
            details = EXCEPTION_UNKNOWN
        raise ConfigEntryNotReady(details) from err

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.unique_id] = {
        UNDO_UPDATE_LISTENER: entry.add_update_listener(_async_update_listener),
        SYNO_API: api,
        SYSTEM_LOADED: True,
    }

    # Services
    await _async_setup_services(hass)

    # For SSDP compat
    if not entry.data.get(CONF_MAC):
        network = await hass.async_add_executor_job(getattr, api.dsm, "network")
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_MAC: network.macs}
        )

    async def async_coordinator_update_data_cameras() -> dict[
        str, dict[str, SynoCamera]
    ] | None:
        """Fetch all camera data from api."""
        if not hass.data[DOMAIN][entry.unique_id][SYSTEM_LOADED]:
            raise UpdateFailed("System not fully loaded")

        if SynoSurveillanceStation.CAMERA_API_KEY not in api.dsm.apis:
            return None

        surveillance_station = api.surveillance_station

        try:
            async with async_timeout.timeout(30):
                await hass.async_add_executor_job(surveillance_station.update)
        except SynologyDSMAPIErrorException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        return {
            "cameras": {
                camera.id: camera for camera in surveillance_station.get_all_cameras()
            }
        }

    async def async_coordinator_update_data_central() -> None:
        """Fetch all device and sensor data from api."""
        try:
            await api.async_update()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        return None

    async def async_coordinator_update_data_switches() -> dict[
        str, dict[str, Any]
    ] | None:
        """Fetch all switch data from api."""
        if not hass.data[DOMAIN][entry.unique_id][SYSTEM_LOADED]:
            raise UpdateFailed("System not fully loaded")
        if SynoSurveillanceStation.HOME_MODE_API_KEY not in api.dsm.apis:
            return None

        surveillance_station = api.surveillance_station

        return {
            "switches": {
                "home_mode": await hass.async_add_executor_job(
                    surveillance_station.get_home_mode_status
                )
            }
        }

    hass.data[DOMAIN][entry.unique_id][COORDINATOR_CAMERAS] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{entry.unique_id}_cameras",
        update_method=async_coordinator_update_data_cameras,
        update_interval=timedelta(seconds=30),
    )

    hass.data[DOMAIN][entry.unique_id][COORDINATOR_CENTRAL] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{entry.unique_id}_central",
        update_method=async_coordinator_update_data_central,
        update_interval=timedelta(
            minutes=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        ),
    )

    hass.data[DOMAIN][entry.unique_id][COORDINATOR_SWITCHES] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{entry.unique_id}_switches",
        update_method=async_coordinator_update_data_switches,
        update_interval=timedelta(seconds=30),
    )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Synology DSM sensors."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry_data = hass.data[DOMAIN][entry.unique_id]
        entry_data[UNDO_UPDATE_LISTENER]()
        await entry_data[SYNO_API].async_unload()
        hass.data[DOMAIN].pop(entry.unique_id)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_setup_services(hass: HomeAssistant) -> None:
    """Service handler setup."""

    async def service_handler(call: ServiceCall) -> None:
        """Handle service call."""
        serial = call.data.get(CONF_SERIAL)
        dsm_devices = hass.data[DOMAIN]

        if serial:
            dsm_device = dsm_devices.get(serial)
        elif len(dsm_devices) == 1:
            dsm_device = next(iter(dsm_devices.values()))
            serial = next(iter(dsm_devices))
        else:
            _LOGGER.error(
                "More than one DSM configured, must specify one of serials %s",
                sorted(dsm_devices),
            )
            return

        if not dsm_device:
            _LOGGER.error("DSM with specified serial %s not found", serial)
            return

        _LOGGER.debug("%s DSM with serial %s", call.service, serial)
        dsm_api = dsm_device[SYNO_API]
        dsm_device[SYSTEM_LOADED] = False
        if call.service == SERVICE_REBOOT:
            await dsm_api.async_reboot()
        elif call.service == SERVICE_SHUTDOWN:
            await dsm_api.async_shutdown()

    for service in SERVICES:
        hass.services.async_register(DOMAIN, service, service_handler)


class SynoApi:
    """Class to interface with Synology DSM API."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the API wrapper class."""
        self._hass = hass
        self._entry = entry
        if entry.data.get(CONF_SSL):
            self.config_url = f"https://{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"
        else:
            self.config_url = f"http://{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"

        self.initialized = False
        # DSM APIs
        self.dsm: SynologyDSM = None
        self.information: SynoDSMInformation = None
        self.network: SynoDSMNetwork = None
        self.security: SynoCoreSecurity = None
        self.storage: SynoStorage = None
        self.surveillance_station: SynoSurveillanceStation = None
        self.system: SynoCoreSystem = None
        self.upgrade: SynoCoreUpgrade = None
        self.utilisation: SynoCoreUtilization = None

        # Should we fetch them
        self._fetching_entities: dict[str, set[str]] = {}
        self._with_information = True
        self._with_security = True
        self._with_storage = True
        self._with_surveillance_station = True
        self._with_system = True
        self._with_upgrade = True
        self._with_utilisation = True

    async def async_setup(self) -> None:
        """Start interacting with the NAS."""
        self.dsm = SynologyDSM(
            self._entry.data[CONF_HOST],
            self._entry.data[CONF_PORT],
            self._entry.data[CONF_USERNAME],
            self._entry.data[CONF_PASSWORD],
            self._entry.data[CONF_SSL],
            self._entry.data[CONF_VERIFY_SSL],
            timeout=self._entry.options.get(CONF_TIMEOUT),
            device_token=self._entry.data.get(CONF_DEVICE_TOKEN),
        )
        await self._hass.async_add_executor_job(self.dsm.login)

        # check if surveillance station is used
        self._with_surveillance_station = bool(
            self.dsm.apis.get(SynoSurveillanceStation.CAMERA_API_KEY)
        )
        _LOGGER.debug(
            "State of Surveillance_station during setup of '%s': %s",
            self._entry.unique_id,
            self._with_surveillance_station,
        )

        self._async_setup_api_requests()

        await self._hass.async_add_executor_job(self._fetch_device_configuration)
        await self.async_update()
        self.initialized = True

    @callback
    def subscribe(self, api_key: str, unique_id: str) -> Callable[[], None]:
        """Subscribe an entity to API fetches."""
        _LOGGER.debug("Subscribe new entity: %s", unique_id)
        if api_key not in self._fetching_entities:
            self._fetching_entities[api_key] = set()
        self._fetching_entities[api_key].add(unique_id)

        @callback
        def unsubscribe() -> None:
            """Unsubscribe an entity from API fetches (when disable)."""
            _LOGGER.debug("Unsubscribe entity: %s", unique_id)
            self._fetching_entities[api_key].remove(unique_id)
            if len(self._fetching_entities[api_key]) == 0:
                self._fetching_entities.pop(api_key)

        return unsubscribe

    @callback
    def _async_setup_api_requests(self) -> None:
        """Determine if we should fetch each API, if one entity needs it."""
        # Entities not added yet, fetch all
        if not self._fetching_entities:
            _LOGGER.debug(
                "Entities not added yet, fetch all for '%s'", self._entry.unique_id
            )
            return

        # surveillance_station is updated by own coordinator
        self.dsm.reset(self.surveillance_station)

        # Determine if we should fetch an API
        self._with_system = bool(self.dsm.apis.get(SynoCoreSystem.API_KEY))
        self._with_security = bool(
            self._fetching_entities.get(SynoCoreSecurity.API_KEY)
        )
        self._with_storage = bool(self._fetching_entities.get(SynoStorage.API_KEY))
        self._with_upgrade = bool(self._fetching_entities.get(SynoCoreUpgrade.API_KEY))
        self._with_utilisation = bool(
            self._fetching_entities.get(SynoCoreUtilization.API_KEY)
        )
        self._with_information = bool(
            self._fetching_entities.get(SynoDSMInformation.API_KEY)
        )

        # Reset not used API, information is not reset since it's used in device_info
        if not self._with_security:
            _LOGGER.debug(
                "Disable security api from being updated for '%s'",
                self._entry.unique_id,
            )
            self.dsm.reset(self.security)
            self.security = None

        if not self._with_storage:
            _LOGGER.debug(
                "Disable storage api from being updatedf or '%s'", self._entry.unique_id
            )
            self.dsm.reset(self.storage)
            self.storage = None

        if not self._with_system:
            _LOGGER.debug(
                "Disable system api from being updated for '%s'", self._entry.unique_id
            )
            self.dsm.reset(self.system)
            self.system = None

        if not self._with_upgrade:
            _LOGGER.debug(
                "Disable upgrade api from being updated for '%s'", self._entry.unique_id
            )
            self.dsm.reset(self.upgrade)
            self.upgrade = None

        if not self._with_utilisation:
            _LOGGER.debug(
                "Disable utilisation api from being updated for '%s'",
                self._entry.unique_id,
            )
            self.dsm.reset(self.utilisation)
            self.utilisation = None

    def _fetch_device_configuration(self) -> None:
        """Fetch initial device config."""
        self.information = self.dsm.information
        self.network = self.dsm.network
        self.network.update()

        if self._with_security:
            _LOGGER.debug("Enable security api updates for '%s'", self._entry.unique_id)
            self.security = self.dsm.security

        if self._with_storage:
            _LOGGER.debug("Enable storage api updates for '%s'", self._entry.unique_id)
            self.storage = self.dsm.storage

        if self._with_upgrade:
            _LOGGER.debug("Enable upgrade api updates for '%s'", self._entry.unique_id)
            self.upgrade = self.dsm.upgrade

        if self._with_system:
            _LOGGER.debug("Enable system api updates for '%s'", self._entry.unique_id)
            self.system = self.dsm.system

        if self._with_utilisation:
            _LOGGER.debug(
                "Enable utilisation api updates for '%s'", self._entry.unique_id
            )
            self.utilisation = self.dsm.utilisation

        if self._with_surveillance_station:
            _LOGGER.debug(
                "Enable surveillance_station api updates for '%s'",
                self._entry.unique_id,
            )
            self.surveillance_station = self.dsm.surveillance_station

    async def async_reboot(self) -> None:
        """Reboot NAS."""
        try:
            await self._hass.async_add_executor_job(self.system.reboot)
        except (SynologyDSMLoginFailedException, SynologyDSMRequestException) as err:
            _LOGGER.error(
                "Reboot of '%s' not possible, please try again later",
                self._entry.unique_id,
            )
            _LOGGER.debug("Exception:%s", err)

    async def async_shutdown(self) -> None:
        """Shutdown NAS."""
        try:
            await self._hass.async_add_executor_job(self.system.shutdown)
        except (SynologyDSMLoginFailedException, SynologyDSMRequestException) as err:
            _LOGGER.error(
                "Shutdown of '%s' not possible, please try again later",
                self._entry.unique_id,
            )
            _LOGGER.debug("Exception:%s", err)

    async def async_unload(self) -> None:
        """Stop interacting with the NAS and prepare for removal from hass."""
        try:
            await self._hass.async_add_executor_job(self.dsm.logout)
        except (SynologyDSMAPIErrorException, SynologyDSMRequestException) as err:
            _LOGGER.debug(
                "Logout from '%s' not possible:%s", self._entry.unique_id, err
            )

    async def async_update(self, now: timedelta | None = None) -> None:
        """Update function for updating API information."""
        _LOGGER.debug("Start data update for '%s'", self._entry.unique_id)
        self._async_setup_api_requests()
        try:
            await self._hass.async_add_executor_job(
                self.dsm.update, self._with_information
            )
        except (SynologyDSMLoginFailedException, SynologyDSMRequestException) as err:
            if not self.initialized:
                raise err

            _LOGGER.warning(
                "Connection error during update, fallback by reloading the entry"
            )
            _LOGGER.debug(
                "Connection error during update of '%s' with exception: %s",
                self._entry.unique_id,
                err,
            )
            await self._hass.config_entries.async_reload(self._entry.entry_id)
            return


class SynologyDSMBaseEntity(CoordinatorEntity):
    """Representation of a Synology NAS entry."""

    entity_description: SynologyDSMEntityDescription
    unique_id: str
    _attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}

    def __init__(
        self,
        api: SynoApi,
        coordinator: DataUpdateCoordinator[dict[str, dict[str, Any]]],
        description: SynologyDSMEntityDescription,
    ) -> None:
        """Initialize the Synology DSM entity."""
        super().__init__(coordinator)
        self.entity_description = description

        self._api = api
        self._attr_name = f"{api.network.hostname} {description.name}"
        self._attr_unique_id: str = (
            f"{api.information.serial}_{description.api_key}:{description.key}"
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._api.information.serial)},
            name="Synology NAS",
            manufacturer="Synology",
            model=self._api.information.model,
            sw_version=self._api.information.version_string,
            configuration_url=self._api.config_url,
        )

    async def async_added_to_hass(self) -> None:
        """Register entity for updates from API."""
        self.async_on_remove(
            self._api.subscribe(self.entity_description.api_key, self.unique_id)
        )
        await super().async_added_to_hass()


class SynologyDSMDeviceEntity(SynologyDSMBaseEntity):
    """Representation of a Synology NAS disk or volume entry."""

    def __init__(
        self,
        api: SynoApi,
        coordinator: DataUpdateCoordinator[dict[str, dict[str, Any]]],
        description: SynologyDSMEntityDescription,
        device_id: str | None = None,
    ) -> None:
        """Initialize the Synology DSM disk or volume entity."""
        super().__init__(api, coordinator, description)
        self._device_id = device_id
        self._device_name: str | None = None
        self._device_manufacturer: str | None = None
        self._device_model: str | None = None
        self._device_firmware: str | None = None
        self._device_type = None

        if "volume" in description.key:
            volume = self._api.storage.get_volume(self._device_id)
            # Volume does not have a name
            self._device_name = volume["id"].replace("_", " ").capitalize()
            self._device_manufacturer = "Synology"
            self._device_model = self._api.information.model
            self._device_firmware = self._api.information.version_string
            self._device_type = (
                volume["device_type"]
                .replace("_", " ")
                .replace("raid", "RAID")
                .replace("shr", "SHR")
            )
        elif "disk" in description.key:
            disk = self._api.storage.get_disk(self._device_id)
            self._device_name = disk["name"]
            self._device_manufacturer = disk["vendor"]
            self._device_model = disk["model"].strip()
            self._device_firmware = disk["firm"]
            self._device_type = disk["diskType"]
        self._name = (
            f"{self._api.network.hostname} {self._device_name} {description.name}"
        )
        self._attr_unique_id += f"_{self._device_id}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._api.storage  # type: ignore [no-any-return]

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._api.information.serial}_{self._device_id}")},
            name=f"Synology NAS ({self._device_name} - {self._device_type})",
            manufacturer=self._device_manufacturer,
            model=self._device_model,
            sw_version=self._device_firmware,
            via_device=(DOMAIN, self._api.information.serial),
            configuration_url=self._api.config_url,
        )
