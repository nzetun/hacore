"""Support for the Skybell HD Doorbell."""
import logging

from requests.exceptions import ConnectTimeout, HTTPError
from skybellpy import Skybell
import voluptuous as vol

from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_PASSWORD,
    CONF_USERNAME,
    __version__,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by Skybell.com"

NOTIFICATION_ID = "skybell_notification"
NOTIFICATION_TITLE = "Skybell Sensor Setup"

DOMAIN = "skybell"
DEFAULT_CACHEDB = "./skybell_cache.pickle"
DEFAULT_ENTITY_NAMESPACE = "skybell"

AGENT_IDENTIFIER = f"HomeAssistant/{__version__}"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the Skybell component."""
    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)

    try:
        cache = hass.config.path(DEFAULT_CACHEDB)
        skybell = Skybell(
            username=username,
            password=password,
            get_devices=True,
            cache_path=cache,
            agent_identifier=AGENT_IDENTIFIER,
        )

        hass.data[DOMAIN] = skybell
    except (ConnectTimeout, HTTPError) as ex:
        _LOGGER.error("Unable to connect to Skybell service: %s", str(ex))
        hass.components.persistent_notification.create(
            "Error: {}<br />"
            "You will need to restart hass after fixing."
            "".format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID,
        )
        return False
    return True


class SkybellDevice(Entity):
    """A HA implementation for Skybell devices."""

    def __init__(self, device):
        """Initialize a sensor for Skybell device."""
        self._device = device

    def update(self):
        """Update automation state."""
        self._device.refresh()

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "device_id": self._device.device_id,
            "status": self._device.status,
            "location": self._device.location,
            "wifi_ssid": self._device.wifi_ssid,
            "wifi_status": self._device.wifi_status,
            "last_check_in": self._device.last_check_in,
            "motion_threshold": self._device.motion_threshold,
            "video_profile": self._device.video_profile,
        }
