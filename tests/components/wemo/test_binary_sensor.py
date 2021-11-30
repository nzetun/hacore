"""Tests for the Wemo binary_sensor entity."""

import pytest

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.wemo.binary_sensor import (
    InsightBinarySensor,
    MakerBinarySensor,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.setup import async_setup_component

from . import entity_test_helpers


class EntityTestHelpers:
    """Common state update helpers."""

    async def test_async_update_locked_multiple_updates(
        self, hass, pywemo_device, wemo_entity
    ):
        """Test that two hass async_update state updates do not proceed at the same time."""
        await entity_test_helpers.test_async_update_locked_multiple_updates(
            hass, pywemo_device, wemo_entity
        )

    async def test_async_update_locked_multiple_callbacks(
        self, hass, pywemo_device, wemo_entity
    ):
        """Test that two device callback state updates do not proceed at the same time."""
        await entity_test_helpers.test_async_update_locked_multiple_callbacks(
            hass, pywemo_device, wemo_entity
        )

    async def test_async_update_locked_callback_and_update(
        self, hass, pywemo_device, wemo_entity
    ):
        """Test that a callback and a state update request can't both happen at the same time.

        When a state update is received via a callback from the device at the same time
        as hass is calling `async_update`, verify that only one of the updates proceeds.
        """
        await entity_test_helpers.test_async_update_locked_callback_and_update(
            hass, pywemo_device, wemo_entity
        )


class TestMotion(EntityTestHelpers):
    """Test for the pyWeMo Motion device."""

    @pytest.fixture
    def pywemo_model(self):
        """Pywemo Motion models use the binary_sensor platform."""
        return "Motion"

    async def test_binary_sensor_registry_state_callback(
        self, hass, pywemo_registry, pywemo_device, wemo_entity
    ):
        """Verify that the binary_sensor receives state updates from the registry."""
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

    async def test_binary_sensor_update_entity(
        self, hass, pywemo_registry, pywemo_device, wemo_entity
    ):
        """Verify that the binary_sensor performs state updates."""
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


class TestMaker(EntityTestHelpers):
    """Test for the pyWeMo Maker device."""

    @pytest.fixture
    def pywemo_model(self):
        """Pywemo Motion models use the binary_sensor platform."""
        return "Maker"

    @pytest.fixture
    def wemo_entity_suffix(self):
        """Select the MakerBinarySensor entity."""
        return MakerBinarySensor._name_suffix.lower()

    @pytest.fixture(name="pywemo_device")
    def pywemo_device_fixture(self, pywemo_device):
        """Fixture for WeMoDevice instances."""
        pywemo_device.maker_params = {
            "hassensor": 1,
            "sensorstate": 1,
            "switchmode": 1,
            "switchstate": 0,
        }
        pywemo_device.has_sensor = pywemo_device.maker_params["hassensor"]
        pywemo_device.sensor_state = pywemo_device.maker_params["sensorstate"]
        yield pywemo_device

    async def test_registry_state_callback(
        self, hass, pywemo_registry, pywemo_device, wemo_entity
    ):
        """Verify that the binary_sensor receives state updates from the registry."""
        # On state.
        pywemo_device.sensor_state = 0
        pywemo_registry.callbacks[pywemo_device.name](pywemo_device, "", "")
        await hass.async_block_till_done()
        assert hass.states.get(wemo_entity.entity_id).state == STATE_ON

        # Off state.
        pywemo_device.sensor_state = 1
        pywemo_registry.callbacks[pywemo_device.name](pywemo_device, "", "")
        await hass.async_block_till_done()
        assert hass.states.get(wemo_entity.entity_id).state == STATE_OFF


class TestInsight(EntityTestHelpers):
    """Test for the pyWeMo Insight device."""

    @pytest.fixture
    def pywemo_model(self):
        """Pywemo Motion models use the binary_sensor platform."""
        return "Insight"

    @pytest.fixture
    def wemo_entity_suffix(self):
        """Select the InsightBinarySensor entity."""
        return InsightBinarySensor._name_suffix.lower()

    @pytest.fixture(name="pywemo_device")
    def pywemo_device_fixture(self, pywemo_device):
        """Fixture for WeMoDevice instances."""
        pywemo_device.insight_params = {
            "currentpower": 1.0,
            "todaymw": 200000000.0,
            "state": "0",
            "onfor": 0,
            "ontoday": 0,
            "ontotal": 0,
            "powerthreshold": 0,
        }
        yield pywemo_device

    async def test_registry_state_callback(
        self, hass, pywemo_registry, pywemo_device, wemo_entity
    ):
        """Verify that the binary_sensor receives state updates from the registry."""
        # On state.
        pywemo_device.get_state.return_value = 1
        pywemo_device.insight_params["state"] = "1"
        pywemo_registry.callbacks[pywemo_device.name](pywemo_device, "", "")
        await hass.async_block_till_done()
        assert hass.states.get(wemo_entity.entity_id).state == STATE_ON

        # Standby (Off) state.
        pywemo_device.get_state.return_value = 1
        pywemo_device.insight_params["state"] = "8"
        pywemo_registry.callbacks[pywemo_device.name](pywemo_device, "", "")
        await hass.async_block_till_done()
        assert hass.states.get(wemo_entity.entity_id).state == STATE_OFF

        # Off state.
        pywemo_device.get_state.return_value = 0
        pywemo_device.insight_params["state"] = "1"
        pywemo_registry.callbacks[pywemo_device.name](pywemo_device, "", "")
        await hass.async_block_till_done()
        assert hass.states.get(wemo_entity.entity_id).state == STATE_OFF
