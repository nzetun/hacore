"""Support for XBee Zigbee lights."""
import voluptuous as vol

from homeassistant.components.light import LightEntity

from . import PLATFORM_SCHEMA, XBeeDigitalOut, XBeeDigitalOutConfig
from .const import CONF_ON_STATE, DEFAULT_ON_STATE, DOMAIN, STATES

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_ON_STATE, default=DEFAULT_ON_STATE): vol.In(STATES)}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create and add an entity based on the configuration."""
    zigbee_device = hass.data[DOMAIN]
    add_entities([XBeeLight(XBeeDigitalOutConfig(config), zigbee_device)])


class XBeeLight(XBeeDigitalOut, LightEntity):
    """Use XBeeDigitalOut as light."""
