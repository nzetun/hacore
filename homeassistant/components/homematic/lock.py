"""Support for Homematic locks."""
from homeassistant.components.lock import SUPPORT_OPEN, LockEntity

from .const import ATTR_DISCOVER_DEVICES
from .entity import HMDevice


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Homematic lock platform."""
    if discovery_info is None:
        return

    devices = []
    for conf in discovery_info[ATTR_DISCOVER_DEVICES]:
        devices.append(HMLock(conf))

    add_entities(devices, True)


class HMLock(HMDevice, LockEntity):
    """Representation of a Homematic lock aka KeyMatic."""

    @property
    def is_locked(self):
        """Return true if the lock is locked."""
        return not bool(self._hm_get_state())

    def lock(self, **kwargs):
        """Lock the lock."""
        self._hmdevice.lock()

    def unlock(self, **kwargs):
        """Unlock the lock."""
        self._hmdevice.unlock()

    def open(self, **kwargs):
        """Open the door latch."""
        self._hmdevice.open()

    def _init_data_struct(self):
        """Generate the data dictionary (self._data) from metadata."""
        self._state = "STATE"
        self._data.update({self._state: None})

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN
