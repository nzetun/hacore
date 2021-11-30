"""Alarm sensors for the Venstar Thermostat."""
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
)

from . import VenstarEntity
from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """Set up Vensar device binary_sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    if coordinator.client.alerts is None:
        return
    async_add_entities(
        VenstarBinarySensor(coordinator, config_entry, alert["name"])
        for alert in coordinator.client.alerts
    )


class VenstarBinarySensor(VenstarEntity, BinarySensorEntity):
    """Represent a Venstar alert."""

    _attr_device_class = DEVICE_CLASS_PROBLEM

    def __init__(self, coordinator, config, alert):
        """Initialize the alert."""
        super().__init__(coordinator, config)
        self.alert = alert
        self._attr_unique_id = f"{config.entry_id}_{alert.replace(' ', '_')}"
        self._attr_name = f"{self._client.name} {alert}"

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        for alert in self._client.alerts:
            if alert["name"] == self.alert:
                return alert["active"]

        return None
