"""Tests for the Wemo switch entity."""

import pytest
from pywemo.exceptions import ActionException

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.setup import async_setup_component

from . import entity_test_helpers


@pytest.fixture
def pywemo_model():
    """Pywemo LightSwitch models use the switch platform."""
    return "LightSwitch"


# Tests that are in common among wemo platforms. These test methods will be run
# in the scope of this test module. They will run using the pywemo_model from
# this test module (LightSwitch).
test_async_update_locked_multiple_updates = (
    entity_test_helpers.test_async_update_locked_multiple_updates
)
test_async_update_locked_multiple_callbacks = (
    entity_test_helpers.test_async_update_locked_multiple_callbacks
)
test_async_update_locked_callback_and_update = (
    entity_test_helpers.test_async_update_locked_callback_and_update
)


async def test_switch_registry_state_callback(
    hass, pywemo_registry, pywemo_device, wemo_entity
):
    """Verify that the switch receives state updates from the registry."""
    # On state.
    pywemo_device.get_state.return_value = 1
    pywemo_registry.callbacks[pywemo_device.name](pywemo_device, "", "")
    await hass.async_block_till_done()
    assert hass.states.get(wemo_entity.entity_id).state == STATE_ON

    # Off state.
    pywemo_device.get_state.return_value = 0
    pywemo_registry.callbacks[pywemo_device.name](pywemo_device, "", "")
    await hass.async_block_till_done()
    assert hass.states.get(wemo_entity.entity_id).state == STATE_OFF


async def test_switch_update_entity(hass, pywemo_registry, pywemo_device, wemo_entity):
    """Verify that the switch performs state updates."""
    await async_setup_component(hass, HA_DOMAIN, {})

    # On state.
    pywemo_device.get_state.return_value = 1
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: [wemo_entity.entity_id]},
        blocking=True,
    )
    assert hass.states.get(wemo_entity.entity_id).state == STATE_ON

    # Off state.
    pywemo_device.get_state.return_value = 0
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: [wemo_entity.entity_id]},
        blocking=True,
    )
    assert hass.states.get(wemo_entity.entity_id).state == STATE_OFF


async def test_available_after_update(
    hass, pywemo_registry, pywemo_device, wemo_entity
):
    """Test the avaliability when an On call fails and after an update."""
    pywemo_device.on.side_effect = ActionException
    pywemo_device.get_state.return_value = 1
    await entity_test_helpers.test_avaliable_after_update(
        hass, pywemo_registry, pywemo_device, wemo_entity, SWITCH_DOMAIN
    )
