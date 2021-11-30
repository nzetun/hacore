"""Test UptimeRobot binary_sensor."""

from unittest.mock import patch

from pyuptimerobot import UptimeRobotAuthenticationException

from homeassistant.components.binary_sensor import DEVICE_CLASS_CONNECTIVITY
from homeassistant.components.uptimerobot.const import (
    ATTRIBUTION,
    COORDINATOR_UPDATE_INTERVAL,
)
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt

from .common import (
    MOCK_UPTIMEROBOT_MONITOR,
    UPTIMEROBOT_TEST_ENTITY,
    setup_uptimerobot_integration,
)

from tests.common import async_fire_time_changed


async def test_presentation(hass: HomeAssistant) -> None:
    """Test the presenstation of UptimeRobot binary_sensors."""
    await setup_uptimerobot_integration(hass)

    entity = hass.states.get(UPTIMEROBOT_TEST_ENTITY)

    assert entity.state == STATE_ON
    assert entity.attributes["device_class"] == DEVICE_CLASS_CONNECTIVITY
    assert entity.attributes["attribution"] == ATTRIBUTION
    assert entity.attributes["target"] == MOCK_UPTIMEROBOT_MONITOR["url"]


async def test_unaviable_on_update_failure(hass: HomeAssistant) -> None:
    """Test entity unaviable on update failure."""
    await setup_uptimerobot_integration(hass)

    entity = hass.states.get(UPTIMEROBOT_TEST_ENTITY)
    assert entity.state == STATE_ON

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_monitors",
        side_effect=UptimeRobotAuthenticationException,
    ):
        async_fire_time_changed(hass, dt.utcnow() + COORDINATOR_UPDATE_INTERVAL)
        await hass.async_block_till_done()

    entity = hass.states.get(UPTIMEROBOT_TEST_ENTITY)
    assert entity.state == STATE_UNAVAILABLE
