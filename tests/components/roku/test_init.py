"""Tests for the Roku integration."""
from unittest.mock import patch

from homeassistant.components.roku.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.components.roku import setup_integration
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_config_entry_not_ready(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the Roku configuration entry not ready."""
    entry = await setup_integration(hass, aioclient_mock, error=True)

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_config_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the Roku configuration entry unloading."""
    with patch(
        "homeassistant.components.roku.media_player.async_setup_entry",
        return_value=True,
    ), patch(
        "homeassistant.components.roku.remote.async_setup_entry",
        return_value=True,
    ):
        entry = await setup_integration(hass, aioclient_mock)

    assert hass.data[DOMAIN][entry.entry_id]
    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.entry_id not in hass.data[DOMAIN]
    assert entry.state is ConfigEntryState.NOT_LOADED
