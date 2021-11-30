"""Sensor platform for Hass.io addons."""
from __future__ import annotations

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ADDONS_COORDINATOR
from .const import (
    ATTR_CPU_PERCENT,
    ATTR_MEMORY_PERCENT,
    ATTR_VERSION,
    ATTR_VERSION_LATEST,
    DATA_KEY_ADDONS,
    DATA_KEY_OS,
)
from .entity import HassioAddonEntity, HassioOSEntity

COMMON_ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        entity_registry_enabled_default=False,
        key=ATTR_VERSION,
        name="Version",
    ),
    SensorEntityDescription(
        entity_registry_enabled_default=False,
        key=ATTR_VERSION_LATEST,
        name="Newest Version",
    ),
)

ADDON_ENTITY_DESCRIPTIONS = COMMON_ENTITY_DESCRIPTIONS + (
    SensorEntityDescription(
        entity_registry_enabled_default=False,
        key=ATTR_CPU_PERCENT,
        name="CPU Percent",
        icon="mdi:cpu-64-bit",
        native_unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        entity_registry_enabled_default=False,
        key=ATTR_MEMORY_PERCENT,
        name="Memory Percent",
        icon="mdi:memory",
        native_unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
)

OS_ENTITY_DESCRIPTIONS = COMMON_ENTITY_DESCRIPTIONS


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sensor set up for Hass.io config entry."""
    coordinator = hass.data[ADDONS_COORDINATOR]

    entities = []

    for addon in coordinator.data[DATA_KEY_ADDONS].values():
        for entity_description in ADDON_ENTITY_DESCRIPTIONS:
            entities.append(
                HassioAddonSensor(
                    addon=addon,
                    coordinator=coordinator,
                    entity_description=entity_description,
                )
            )

    if coordinator.is_hass_os:
        for entity_description in OS_ENTITY_DESCRIPTIONS:
            entities.append(
                HassioOSSensor(
                    coordinator=coordinator,
                    entity_description=entity_description,
                )
            )

    async_add_entities(entities)


class HassioAddonSensor(HassioAddonEntity, SensorEntity):
    """Sensor to track a Hass.io add-on attribute."""

    @property
    def native_value(self) -> str:
        """Return native value of entity."""
        return self.coordinator.data[DATA_KEY_ADDONS][self._addon_slug][
            self.entity_description.key
        ]


class HassioOSSensor(HassioOSEntity, SensorEntity):
    """Sensor to track a Hass.io add-on attribute."""

    @property
    def native_value(self) -> str:
        """Return native value of entity."""
        return self.coordinator.data[DATA_KEY_OS][self.entity_description.key]
