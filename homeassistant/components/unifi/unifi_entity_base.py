"""Base class for UniFi Network entities."""
import logging
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_registry import async_entries_for_device

_LOGGER = logging.getLogger(__name__)


class UniFiBase(Entity):
    """UniFi entity base class."""

    DOMAIN = ""
    TYPE = ""

    def __init__(self, item, controller) -> None:
        """Set up UniFi Network entity base.

        Register mac to controller entities to cover disabled entities.
        """
        self._item = item
        self.controller = controller
        self.controller.entities[self.DOMAIN][self.TYPE].add(self.key)

    @property
    def key(self) -> Any:
        """Return item key."""
        return self._item.mac

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        _LOGGER.debug(
            "New %s entity %s (%s)",
            self.TYPE,
            self.entity_id,
            self.key,
        )
        for signal, method in (
            (self.controller.signal_reachable, self.async_signal_reachable_callback),
            (self.controller.signal_options_update, self.options_updated),
            (self.controller.signal_remove, self.remove_item),
        ):
            self.async_on_remove(async_dispatcher_connect(self.hass, signal, method))
        self._item.register_callback(self.async_update_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect object when removed."""
        _LOGGER.debug(
            "Removing %s entity %s (%s)",
            self.TYPE,
            self.entity_id,
            self.key,
        )
        self._item.remove_callback(self.async_update_callback)
        self.controller.entities[self.DOMAIN][self.TYPE].remove(self.key)

    @callback
    def async_signal_reachable_callback(self) -> None:
        """Call when controller connection state change."""
        self.async_update_callback()

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        _LOGGER.debug(
            "Updating %s entity %s (%s)",
            self.TYPE,
            self.entity_id,
            self.key,
        )
        self.async_write_ha_state()

    async def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        raise NotImplementedError

    async def remove_item(self, keys: set) -> None:
        """Remove entity if key is part of set.

        Remove entity if no entry in entity registry exist.
        Remove entity registry entry if no entry in device registry exist.
        Remove device registry entry if there is only one linked entity (this entity).
        Remove config entry reference from device registry entry if there is more than one config entry.
        Remove entity registry entry if there are more than one entity linked to the device registry entry.
        """
        if self.key not in keys:
            return

        entity_registry = er.async_get(self.hass)
        entity_entry = entity_registry.async_get(self.entity_id)
        if not entity_entry:
            await self.async_remove(force_remove=True)
            return

        device_registry = dr.async_get(self.hass)
        device_entry = device_registry.async_get(entity_entry.device_id)
        if not device_entry:
            entity_registry.async_remove(self.entity_id)
            return

        if (
            len(
                entries_for_device := async_entries_for_device(
                    entity_registry,
                    entity_entry.device_id,
                    include_disabled_entities=True,
                )
            )
        ) == 1:
            device_registry.async_remove_device(device_entry.id)
            return

        if (
            len(
                entries_for_device_from_this_config_entry := [
                    entry_for_device
                    for entry_for_device in entries_for_device
                    if entry_for_device.config_entry_id
                    == self.controller.config_entry.entry_id
                ]
            )
            != len(entries_for_device)
            and len(entries_for_device_from_this_config_entry) == 1
        ):
            device_registry.async_update_device(
                entity_entry.device_id,
                remove_config_entry_id=self.controller.config_entry.entry_id,
            )

        entity_registry.async_remove(self.entity_id)

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False
