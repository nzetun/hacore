"""BleBox devices setup tests."""

import logging

import blebox_uniapi

from homeassistant.components.blebox.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState

from .conftest import mock_config, patch_product_identify


async def test_setup_failure(hass, caplog):
    """Test that setup failure is handled and logged."""

    patch_product_identify(None, side_effect=blebox_uniapi.error.ClientError)

    entry = mock_config()
    entry.add_to_hass(hass)

    caplog.set_level(logging.ERROR)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert "Identify failed at 172.100.123.4:80 ()" in caplog.text
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_failure_on_connection(hass, caplog):
    """Test that setup failure is handled and logged."""

    patch_product_identify(None, side_effect=blebox_uniapi.error.ConnectionError)

    entry = mock_config()
    entry.add_to_hass(hass)

    caplog.set_level(logging.ERROR)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert "Identify failed at 172.100.123.4:80 ()" in caplog.text
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_config_entry(hass):
    """Test that unloading works properly."""
    patch_product_identify(None)

    entry = mock_config()
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.data[DOMAIN]

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.data.get(DOMAIN)

    assert entry.state is ConfigEntryState.NOT_LOADED
