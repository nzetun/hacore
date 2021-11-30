"""Platform for the opengarage.io binary sensor component."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import callback

from .const import DOMAIN
from .entity import OpenGarageEntity

_LOGGER = logging.getLogger(__name__)


SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="vehicle",
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the OpenGarage binary sensors."""
    open_garage_data_coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            OpenGarageBinarySensor(
                open_garage_data_coordinator,
                entry.unique_id,
                description,
            )
            for description in SENSOR_TYPES
        ],
    )


class OpenGarageBinarySensor(OpenGarageEntity, BinarySensorEntity):
    """Representation of a OpenGarage binary sensor."""

    def __init__(self, open_garage_data_coordinator, device_id, description):
        """Initialize the entity."""
        self._available = False
        super().__init__(open_garage_data_coordinator, device_id, description)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._available

    @callback
    def _update_attr(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_name = (
            f'{self.coordinator.data["name"]} {self.entity_description.key}'
        )
        state = self.coordinator.data.get(self.entity_description.key)
        if state == 1:
            self._attr_is_on = True
            self._available = True
        elif state == 0:
            self._attr_is_on = False
            self._available = True
        else:
            self._available = False
