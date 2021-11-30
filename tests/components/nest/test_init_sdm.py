"""
Test for setup methods for the SDM API.

The tests fake out the subscriber/devicemanager and simulate setup behavior
and failure modes.
"""

import copy
import logging
from unittest.mock import patch

from google_nest_sdm.exceptions import AuthException, GoogleNestException

from homeassistant.components.nest import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.setup import async_setup_component

from .common import CONFIG, async_setup_sdm_platform, create_config_entry

PLATFORM = "sensor"


async def test_setup_success(hass, caplog):
    """Test successful setup."""
    with caplog.at_level(logging.ERROR, logger="homeassistant.components.nest"):
        await async_setup_sdm_platform(hass, PLATFORM)
        assert not caplog.records

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED


async def async_setup_sdm(hass, config=CONFIG):
    """Prepare test setup."""
    create_config_entry(hass)
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation"
    ):
        return await async_setup_component(hass, DOMAIN, config)


async def test_setup_configuration_failure(hass, caplog):
    """Test configuration error."""
    config = copy.deepcopy(CONFIG)
    config[DOMAIN]["subscriber_id"] = "invalid-subscriber-format"

    result = await async_setup_sdm(hass, config)
    assert result

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_ERROR

    # This error comes from the python google-nest-sdm library, as a check added
    # to prevent common misconfigurations (e.g. confusing topic and subscriber)
    assert "Subscription misconfigured. Expected subscriber_id" in caplog.text


async def test_setup_susbcriber_failure(hass, caplog):
    """Test configuration error."""
    with patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber.start_async",
        side_effect=GoogleNestException(),
    ), caplog.at_level(logging.ERROR, logger="homeassistant.components.nest"):
        result = await async_setup_sdm(hass)
        assert result
        assert "Subscriber error:" in caplog.text

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_RETRY


async def test_setup_device_manager_failure(hass, caplog):
    """Test configuration error."""
    with patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber.start_async"
    ), patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber.async_get_device_manager",
        side_effect=GoogleNestException(),
    ), caplog.at_level(
        logging.ERROR, logger="homeassistant.components.nest"
    ):
        result = await async_setup_sdm(hass)
        assert result
        assert len(caplog.messages) == 1
        assert "Device manager error:" in caplog.text

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_RETRY


async def test_subscriber_auth_failure(hass, caplog):
    """Test configuration error."""
    with patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber.start_async",
        side_effect=AuthException(),
    ):
        result = await async_setup_sdm(hass, CONFIG)
        assert result

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


async def test_setup_missing_subscriber_id(hass, caplog):
    """Test successful setup."""
    config = copy.deepcopy(CONFIG)
    del config[DOMAIN]["subscriber_id"]
    with caplog.at_level(logging.ERROR, logger="homeassistant.components.nest"):
        result = await async_setup_sdm(hass, config)
        assert not result
        assert "Configuration option" in caplog.text

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.NOT_LOADED


async def test_empty_config(hass, caplog):
    """Test successful setup."""
    with caplog.at_level(logging.ERROR, logger="homeassistant.components.nest"):
        result = await async_setup_component(hass, DOMAIN, {})
        assert result
        assert not caplog.records

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 0
