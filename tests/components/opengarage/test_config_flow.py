"""Test the OpenGarage config flow."""
from unittest.mock import patch

import aiohttp

from homeassistant import config_entries
from homeassistant.components.opengarage.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "opengarage.OpenGarage.update_state",
        return_value={"name": "Name of the device", "mac": "unique"},
    ), patch(
        "homeassistant.components.opengarage.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "http://1.1.1.1", "device_key": "AfsasdnfkjDD"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Name of the device"
    assert result2["data"] == {
        "host": "http://1.1.1.1",
        "device_key": "AfsasdnfkjDD",
        "port": 80,
        "verify_ssl": False,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "opengarage.OpenGarage.update_state",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "http://1.1.1.1", "device_key": "AfsasdnfkjDD"},
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "opengarage.OpenGarage.update_state",
        side_effect=aiohttp.ClientError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "http://1.1.1.1", "device_key": "AfsasdnfkjDD"},
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "opengarage.OpenGarage.update_state",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "http://1.1.1.1", "device_key": "AfsasdnfkjDD"},
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_flow_entry_already_exists(hass: HomeAssistant) -> None:
    """Test user input for config_entry that already exists."""
    first_entry = MockConfigEntry(
        domain="opengarage",
        data={
            "host": "http://1.1.1.1",
            "device_key": "AfsasdnfkjDD",
        },
        unique_id="unique",
    )
    first_entry.add_to_hass(hass)

    with patch(
        "opengarage.OpenGarage.update_state",
        return_value={"name": "Name of the device", "mac": "unique"},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                "host": "http://1.1.1.1",
                "device_key": "AfsasdnfkjDD",
                "port": 80,
                "verify_ssl": False,
            },
        )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_step_import(hass: HomeAssistant) -> None:
    """Test when import configuring from yaml."""
    with patch(
        "opengarage.OpenGarage.update_state",
        return_value={"name": "Name of the device", "mac": "unique"},
    ), patch(
        "homeassistant.components.opengarage.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "host": "1.1.1.1",
                "device_key": "AfsasdnfkjDD",
                "port": 1234,
                "verify_ssl": False,
                "ssl": False,
            },
        )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Name of the device"
    assert result["data"] == {
        "host": "http://1.1.1.1",
        "device_key": "AfsasdnfkjDD",
        "port": 1234,
        "verify_ssl": False,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_step_import_ssl(hass: HomeAssistant) -> None:
    """Test when import configuring from yaml."""
    with patch(
        "opengarage.OpenGarage.update_state",
        return_value={"name": "Name of the device", "mac": "unique"},
    ), patch(
        "homeassistant.components.opengarage.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "host": "1.1.1.1",
                "device_key": "AfsasdnfkjDD",
                "port": 1234,
                "verify_ssl": False,
                "ssl": True,
            },
        )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Name of the device"
    assert result["data"] == {
        "host": "https://1.1.1.1",
        "device_key": "AfsasdnfkjDD",
        "port": 1234,
        "verify_ssl": False,
    }
    assert len(mock_setup_entry.mock_calls) == 1
