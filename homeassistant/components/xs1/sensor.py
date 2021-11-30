"""Support for XS1 sensors."""
from xs1_api_client.api_constants import ActuatorType

from homeassistant.components.sensor import SensorEntity

from . import ACTUATORS, DOMAIN as COMPONENT_DOMAIN, SENSORS, XS1DeviceEntity


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the XS1 sensor platform."""
    sensors = hass.data[COMPONENT_DOMAIN][SENSORS]
    actuators = hass.data[COMPONENT_DOMAIN][ACTUATORS]

    sensor_entities = []
    for sensor in sensors:
        belongs_to_climate_actuator = False
        for actuator in actuators:
            if (
                actuator.type() == ActuatorType.TEMPERATURE
                and actuator.name() in sensor.name()
            ):
                belongs_to_climate_actuator = True
                break

        if not belongs_to_climate_actuator:
            sensor_entities.append(XS1Sensor(sensor))

    add_entities(sensor_entities)


class XS1Sensor(XS1DeviceEntity, SensorEntity):
    """Representation of a Sensor."""

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.device.name()

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.device.value()

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self.device.unit()
