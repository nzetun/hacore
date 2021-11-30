"""Support for getting information from Arduino pins."""
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

from . import DOMAIN

CONF_PINS = "pins"
CONF_TYPE = "analog"

PIN_SCHEMA = vol.Schema({vol.Required(CONF_NAME): cv.string})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_PINS): vol.Schema({cv.positive_int: PIN_SCHEMA})}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Arduino platform."""
    board = hass.data[DOMAIN]

    pins = config[CONF_PINS]

    sensors = []
    for pinnum, pin in pins.items():
        sensors.append(ArduinoSensor(pin.get(CONF_NAME), pinnum, CONF_TYPE, board))
    add_entities(sensors)


class ArduinoSensor(SensorEntity):
    """Representation of an Arduino Sensor."""

    def __init__(self, name, pin, pin_type, board):
        """Initialize the sensor."""
        self._pin = pin
        self._attr_name = name

        board.set_mode(self._pin, "in", pin_type)
        self._board = board

    def update(self):
        """Get the latest value from the pin."""
        self._attr_native_value = self._board.get_analog_inputs()[self._pin][1]
