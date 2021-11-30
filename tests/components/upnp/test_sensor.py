"""Tests for UPnP/IGD sensor."""

from datetime import timedelta
from unittest.mock import AsyncMock

from homeassistant.components.upnp.const import (
    BYTES_RECEIVED,
    BYTES_SENT,
    DOMAIN,
    PACKETS_RECEIVED,
    PACKETS_SENT,
    ROUTER_IP,
    ROUTER_UPTIME,
    TIMESTAMP,
    UPDATE_INTERVAL,
    WAN_STATUS,
)
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from .conftest import MockDevice

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_upnp_sensors(hass: HomeAssistant, setup_integration: MockConfigEntry):
    """Test normal sensors."""
    mock_device: MockDevice = hass.data[DOMAIN][setup_integration.entry_id].device

    # First poll.
    b_received_state = hass.states.get("sensor.mock_name_b_received")
    b_sent_state = hass.states.get("sensor.mock_name_b_sent")
    packets_received_state = hass.states.get("sensor.mock_name_packets_received")
    packets_sent_state = hass.states.get("sensor.mock_name_packets_sent")
    external_ip_state = hass.states.get("sensor.mock_name_external_ip")
    wan_status_state = hass.states.get("sensor.mock_name_wan_status")
    assert b_received_state.state == "0"
    assert b_sent_state.state == "0"
    assert packets_received_state.state == "0"
    assert packets_sent_state.state == "0"
    assert external_ip_state.state == "8.9.10.11"
    assert wan_status_state.state == "Connected"

    # Second poll.
    mock_device.async_get_traffic_data = AsyncMock(
        return_value={
            TIMESTAMP: mock_device._timestamp + UPDATE_INTERVAL,
            BYTES_RECEIVED: 10240,
            BYTES_SENT: 20480,
            PACKETS_RECEIVED: 30,
            PACKETS_SENT: 40,
        }
    )
    mock_device.async_get_status = AsyncMock(
        return_value={
            WAN_STATUS: "Disconnected",
            ROUTER_UPTIME: 100,
            ROUTER_IP: "",
        }
    )
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()

    b_received_state = hass.states.get("sensor.mock_name_b_received")
    b_sent_state = hass.states.get("sensor.mock_name_b_sent")
    packets_received_state = hass.states.get("sensor.mock_name_packets_received")
    packets_sent_state = hass.states.get("sensor.mock_name_packets_sent")
    external_ip_state = hass.states.get("sensor.mock_name_external_ip")
    wan_status_state = hass.states.get("sensor.mock_name_wan_status")
    assert b_received_state.state == "10240"
    assert b_sent_state.state == "20480"
    assert packets_received_state.state == "30"
    assert packets_sent_state.state == "40"
    assert external_ip_state.state == ""
    assert wan_status_state.state == "Disconnected"


async def test_derived_upnp_sensors(
    hass: HomeAssistant, setup_integration: MockConfigEntry
):
    """Test derived sensors."""
    mock_device: MockDevice = hass.data[DOMAIN][setup_integration.entry_id].device

    # First poll.
    kib_s_received_state = hass.states.get("sensor.mock_name_kib_s_received")
    kib_s_sent_state = hass.states.get("sensor.mock_name_kib_s_sent")
    packets_s_received_state = hass.states.get("sensor.mock_name_packets_s_received")
    packets_s_sent_state = hass.states.get("sensor.mock_name_packets_s_sent")
    assert kib_s_received_state.state == "unknown"
    assert kib_s_sent_state.state == "unknown"
    assert packets_s_received_state.state == "unknown"
    assert packets_s_sent_state.state == "unknown"

    # Second poll.
    mock_device.async_get_traffic_data = AsyncMock(
        return_value={
            TIMESTAMP: mock_device._timestamp + UPDATE_INTERVAL,
            BYTES_RECEIVED: int(10240 * UPDATE_INTERVAL.total_seconds()),
            BYTES_SENT: int(20480 * UPDATE_INTERVAL.total_seconds()),
            PACKETS_RECEIVED: int(30 * UPDATE_INTERVAL.total_seconds()),
            PACKETS_SENT: int(40 * UPDATE_INTERVAL.total_seconds()),
        }
    )
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()

    kib_s_received_state = hass.states.get("sensor.mock_name_kib_s_received")
    kib_s_sent_state = hass.states.get("sensor.mock_name_kib_s_sent")
    packets_s_received_state = hass.states.get("sensor.mock_name_packets_s_received")
    packets_s_sent_state = hass.states.get("sensor.mock_name_packets_s_sent")
    assert kib_s_received_state.state == "10.0"
    assert kib_s_sent_state.state == "20.0"
    assert packets_s_received_state.state == "30.0"
    assert packets_s_sent_state.state == "40.0"
