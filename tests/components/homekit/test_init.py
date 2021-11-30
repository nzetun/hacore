"""Test HomeKit initialization."""
from unittest.mock import patch

from homeassistant.components import logbook
from homeassistant.components.homekit.const import (
    ATTR_DISPLAY_NAME,
    ATTR_VALUE,
    DOMAIN as DOMAIN_HOMEKIT,
    EVENT_HOMEKIT_CHANGED,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_SERVICE
from homeassistant.setup import async_setup_component

from tests.components.logbook.test_init import MockLazyEventPartialState


async def test_humanify_homekit_changed_event(hass, hk_driver, mock_get_source_ip):
    """Test humanifying HomeKit changed event."""
    hass.config.components.add("recorder")
    with patch("homeassistant.components.homekit.HomeKit"):
        assert await async_setup_component(hass, "homekit", {"homekit": {}})
    assert await async_setup_component(hass, "logbook", {})
    entity_attr_cache = logbook.EntityAttributeCache(hass)

    event1, event2 = list(
        logbook.humanify(
            hass,
            [
                MockLazyEventPartialState(
                    EVENT_HOMEKIT_CHANGED,
                    {
                        ATTR_ENTITY_ID: "lock.front_door",
                        ATTR_DISPLAY_NAME: "Front Door",
                        ATTR_SERVICE: "lock",
                    },
                ),
                MockLazyEventPartialState(
                    EVENT_HOMEKIT_CHANGED,
                    {
                        ATTR_ENTITY_ID: "cover.window",
                        ATTR_DISPLAY_NAME: "Window",
                        ATTR_SERVICE: "set_cover_position",
                        ATTR_VALUE: 75,
                    },
                ),
            ],
            entity_attr_cache,
            {},
        )
    )

    assert event1["name"] == "HomeKit"
    assert event1["domain"] == DOMAIN_HOMEKIT
    assert event1["message"] == "send command lock for Front Door"
    assert event1["entity_id"] == "lock.front_door"

    assert event2["name"] == "HomeKit"
    assert event2["domain"] == DOMAIN_HOMEKIT
    assert event2["message"] == "send command set_cover_position to 75 for Window"
    assert event2["entity_id"] == "cover.window"
