"""Test smarttub setup process."""

import asyncio
from unittest.mock import patch

from smarttub import LoginFailed

from homeassistant.components import smarttub
from homeassistant.components.smarttub.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.setup import async_setup_component


async def test_setup_with_no_config(setup_component, hass, smarttub_api):
    """Test that we do not discover anything."""

    # No flows started
    assert len(hass.config_entries.flow.async_progress()) == 0

    smarttub_api.login.assert_not_called()


async def test_setup_entry_not_ready(setup_component, hass, config_entry, smarttub_api):
    """Test setup when the entry is not ready."""
    smarttub_api.login.side_effect = asyncio.TimeoutError

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_auth_failed(setup_component, hass, config_entry, smarttub_api):
    """Test setup when the credentials are invalid."""
    smarttub_api.login.side_effect = LoginFailed

    config_entry.add_to_hass(hass)
    with patch.object(hass.config_entries.flow, "async_init") as mock_flow_init:
        await hass.config_entries.async_setup(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.SETUP_ERROR
        mock_flow_init.assert_called_with(
            DOMAIN,
            context={
                "source": SOURCE_REAUTH,
                "entry_id": config_entry.entry_id,
                "unique_id": config_entry.unique_id,
            },
            data=config_entry.data,
        )


async def test_config_passed_to_config_entry(hass, config_entry, config_data):
    """Test that configured options are loaded via config entry."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, smarttub.DOMAIN, config_data)


async def test_unload_entry(hass, config_entry):
    """Test being able to unload an entry."""
    config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, smarttub.DOMAIN, {}) is True

    assert await hass.config_entries.async_unload(config_entry.entry_id)
