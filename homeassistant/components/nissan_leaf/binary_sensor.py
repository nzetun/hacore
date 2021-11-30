"""Plugged In Status Support for the Nissan Leaf."""
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY_CHARGING,
    DEVICE_CLASS_PLUG,
    BinarySensorEntity,
)

from . import DATA_CHARGING, DATA_LEAF, DATA_PLUGGED_IN, LeafEntity

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up of a Nissan Leaf binary sensor."""
    if discovery_info is None:
        return

    devices = []
    for vin, datastore in hass.data[DATA_LEAF].items():
        _LOGGER.debug("Adding binary_sensors for vin=%s", vin)
        devices.append(LeafPluggedInSensor(datastore))
        devices.append(LeafChargingSensor(datastore))

    add_entities(devices, True)


class LeafPluggedInSensor(LeafEntity, BinarySensorEntity):
    """Plugged In Sensor class."""

    _attr_device_class = DEVICE_CLASS_PLUG

    @property
    def name(self):
        """Sensor name."""
        return f"{self.car.leaf.nickname} Plug Status"

    @property
    def available(self):
        """Sensor availability."""
        return self.car.data[DATA_PLUGGED_IN] is not None

    @property
    def is_on(self):
        """Return true if plugged in."""
        return self.car.data[DATA_PLUGGED_IN]


class LeafChargingSensor(LeafEntity, BinarySensorEntity):
    """Charging Sensor class."""

    _attr_device_class = DEVICE_CLASS_BATTERY_CHARGING

    @property
    def name(self):
        """Sensor name."""
        return f"{self.car.leaf.nickname} Charging Status"

    @property
    def available(self):
        """Sensor availability."""
        return self.car.data[DATA_CHARGING] is not None

    @property
    def is_on(self):
        """Return true if charging."""
        return self.car.data[DATA_CHARGING]
