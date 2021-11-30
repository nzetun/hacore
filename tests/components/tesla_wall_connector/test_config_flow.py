"""Test the Tesla Wall Connector config flow."""
from unittest.mock import patch

from tesla_wall_connector.exceptions import WallConnectorConnectionError

from homeassistant import config_entries, setup
from homeassistant.components.dhcp import HOSTNAME, IP_ADDRESS, MAC_ADDRESS
from homeassistant.components.tesla_wall_connector.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

from tests.common import MockConfigEntry


async def test_form(mock_wall_connector_version, hass: HomeAssistant) -> None:
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.tesla_wall_connector.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Tesla Wall Connector"
    assert result2["data"] == {CONF_HOST: "1.1.1.1"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "tesla_wall_connector.WallConnector.async_get_version",
        side_effect=WallConnectorConnectionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_other_error(
    mock_wall_connector_version, hass: HomeAssistant
) -> None:
    """Test we handle any other error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "tesla_wall_connector.WallConnector.async_get_version",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_already_configured(mock_wall_connector_version, hass):
    """Test we get already configured."""

    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="abc123", data={CONF_HOST: "0.0.0.0"}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.tesla_wall_connector.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )
        await hass.async_block_till_done()

        assert result2["type"] == "abort"
        assert result2["reason"] == "already_configured"

    # Test config entry got updated with latest IP
    assert entry.data[CONF_HOST] == "1.1.1.1"


async def test_dhcp_can_finish(mock_wall_connector_version, hass):
    """Test DHCP discovery flow can finish right away."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data={
            HOSTNAME: "teslawallconnector_abc",
            IP_ADDRESS: "1.2.3.4",
            MAC_ADDRESS: "DC:44:27:12:12",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {CONF_HOST: "1.2.3.4"}


async def test_dhcp_already_exists(mock_wall_connector_version, hass):
    """Test DHCP discovery flow when device already exists."""

    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="abc123", data={CONF_HOST: "1.2.3.4"}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data={
            HOSTNAME: "teslawallconnector_aabbcc",
            IP_ADDRESS: "1.2.3.4",
            MAC_ADDRESS: "aa:bb:cc:dd:ee:ff",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_dhcp_error_from_wall_connector(mock_wall_connector_version, hass):
    """Test DHCP discovery flow when we cannot communicate with the device."""

    with patch(
        "tesla_wall_connector.WallConnector.async_get_version",
        side_effect=WallConnectorConnectionError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data={
                HOSTNAME: "teslawallconnector_aabbcc",
                IP_ADDRESS: "1.2.3.4",
                MAC_ADDRESS: "aa:bb:cc:dd:ee:ff",
            },
        )
        await hass.async_block_till_done()

        assert result["type"] == "abort"
        assert result["reason"] == "cannot_connect"


async def test_option_flow(hass):
    """Test option flow."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="abc123", data={CONF_HOST: "1.2.3.4"}
    )
    entry.add_to_hass(hass)

    assert not entry.options

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        data=None,
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SCAN_INTERVAL: 30},
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {CONF_SCAN_INTERVAL: 30}
