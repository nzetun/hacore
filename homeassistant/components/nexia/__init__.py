"""Support for Nexia / Trane XL Thermostats."""
from functools import partial
import logging

from nexia.const import BRAND_NEXIA
from nexia.home import NexiaHome
from requests.exceptions import ConnectTimeout, HTTPError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv

from .const import CONF_BRAND, DOMAIN, PLATFORMS
from .coordinator import NexiaDataUpdateCoordinator
from .util import is_invalid_auth_code

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.deprecated(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configure the base Nexia device for Home Assistant."""

    conf = entry.data
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]
    brand = conf.get(CONF_BRAND, BRAND_NEXIA)

    state_file = hass.config.path(f"nexia_config_{username}.conf")

    try:
        nexia_home = await hass.async_add_executor_job(
            partial(
                NexiaHome,
                username=username,
                password=password,
                device_name=hass.config.location_name,
                state_file=state_file,
                brand=brand,
            )
        )
    except ConnectTimeout as ex:
        _LOGGER.error("Unable to connect to Nexia service: %s", ex)
        raise ConfigEntryNotReady from ex
    except HTTPError as http_ex:
        if is_invalid_auth_code(http_ex.response.status_code):
            _LOGGER.error(
                "Access error from Nexia service, please check credentials: %s", http_ex
            )
            return False
        _LOGGER.error("HTTP error from Nexia service: %s", http_ex)
        raise ConfigEntryNotReady from http_ex

    coordinator = NexiaDataUpdateCoordinator(hass, nexia_home)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
