"""Platform for the opengarage.io sensor component."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
    ENTITY_CATEGORY_DIAGNOSTIC,
    LENGTH_CENTIMETERS,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    TEMP_CELSIUS,
)
from homeassistant.core import callback

from .const import DOMAIN
from .entity import OpenGarageEntity

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="dist",
        native_unit_of_measurement=LENGTH_CENTIMETERS,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="rssi",
        device_class=DEVICE_CLASS_SIGNAL_STRENGTH,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="temp",
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humid",
        device_class=DEVICE_CLASS_HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the OpenGarage sensors."""
    open_garage_data_coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            OpenGarageSensor(
                open_garage_data_coordinator,
                entry.unique_id,
                description,
            )
            for description in SENSOR_TYPES
            if description.key in open_garage_data_coordinator.data
        ],
    )


class OpenGarageSensor(OpenGarageEntity, SensorEntity):
    """Representation of a OpenGarage sensor."""

    @callback
    def _update_attr(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_name = (
            f'{self.coordinator.data["name"]} {self.entity_description.key}'
        )
        self._attr_native_value = self.coordinator.data.get(self.entity_description.key)
