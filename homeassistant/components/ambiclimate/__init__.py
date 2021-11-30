"""Support for Ambiclimate devices."""
import voluptuous as vol

from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers import config_validation as cv

from . import config_flow
from .const import DOMAIN

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config) -> bool:
    """Set up Ambiclimate components."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    config_flow.register_flow_implementation(
        hass, conf[CONF_CLIENT_ID], conf[CONF_CLIENT_SECRET]
    )

    return True


async def async_setup_entry(hass, entry) -> bool:
    """Set up Ambiclimate from a config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "climate")
    )

    return True
