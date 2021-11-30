"""Support for RFXtrx switches."""
import logging

import RFXtrx as rfxtrxmod

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_DEVICES, STATE_ON
from homeassistant.core import callback

from . import (
    DEFAULT_SIGNAL_REPETITIONS,
    DOMAIN,
    RfxtrxCommandEntity,
    connect_auto_add,
    get_device_id,
    get_rfx_object,
)
from .const import (
    COMMAND_OFF_LIST,
    COMMAND_ON_LIST,
    CONF_DATA_BITS,
    CONF_SIGNAL_REPETITIONS,
)

DATA_SWITCH = f"{DOMAIN}_switch"

_LOGGER = logging.getLogger(__name__)


def supported(event):
    """Return whether an event supports switch."""
    return (
        isinstance(event.device, rfxtrxmod.LightingDevice)
        and not event.device.known_to_be_dimmable
        and not event.device.known_to_be_rollershutter
        or isinstance(event.device, rfxtrxmod.RfyDevice)
    )


async def async_setup_entry(
    hass,
    config_entry,
    async_add_entities,
):
    """Set up config entry."""
    discovery_info = config_entry.data
    device_ids = set()

    # Add switch from config file
    entities = []
    for packet_id, entity_info in discovery_info[CONF_DEVICES].items():
        if (event := get_rfx_object(packet_id)) is None:
            _LOGGER.error("Invalid device: %s", packet_id)
            continue
        if not supported(event):
            continue

        device_id = get_device_id(
            event.device, data_bits=entity_info.get(CONF_DATA_BITS)
        )
        if device_id in device_ids:
            continue
        device_ids.add(device_id)

        entity = RfxtrxSwitch(
            event.device, device_id, entity_info.get(CONF_SIGNAL_REPETITIONS, 1)
        )
        entities.append(entity)

    async_add_entities(entities)

    @callback
    def switch_update(event, device_id):
        """Handle sensor updates from the RFXtrx gateway."""
        if not supported(event):
            return

        if device_id in device_ids:
            return
        device_ids.add(device_id)

        _LOGGER.info(
            "Added switch (Device ID: %s Class: %s Sub: %s, Event: %s)",
            event.device.id_string.lower(),
            event.device.__class__.__name__,
            event.device.subtype,
            "".join(f"{x:02x}" for x in event.data),
        )

        entity = RfxtrxSwitch(
            event.device, device_id, DEFAULT_SIGNAL_REPETITIONS, event=event
        )
        async_add_entities([entity])

    # Subscribe to main RFXtrx events
    connect_auto_add(hass, discovery_info, switch_update)


class RfxtrxSwitch(RfxtrxCommandEntity, SwitchEntity):
    """Representation of a RFXtrx switch."""

    async def async_added_to_hass(self):
        """Restore device state."""
        await super().async_added_to_hass()

        if self._event is None:
            old_state = await self.async_get_last_state()
            if old_state is not None:
                self._state = old_state.state == STATE_ON

    def _apply_event(self, event):
        """Apply command from rfxtrx."""
        super()._apply_event(event)
        if event.values["Command"] in COMMAND_ON_LIST:
            self._state = True
        elif event.values["Command"] in COMMAND_OFF_LIST:
            self._state = False

    @callback
    def _handle_event(self, event, device_id):
        """Check if event applies to me and update."""
        if self._event_applies(event, device_id):
            self._apply_event(event)

            self.async_write_ha_state()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self._async_send(self._device.send_on)
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self._async_send(self._device.send_off)
        self._state = False
        self.async_write_ha_state()
