"""Tests for the Elgato Key Light integration."""

from homeassistant.components.elgato.const import CONF_SERIAL_NUMBER, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


async def init_integration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    skip_setup: bool = False,
    color: bool = False,
    mode_color: bool = False,
) -> MockConfigEntry:
    """Set up the Elgato Key Light integration in Home Assistant."""
    aioclient_mock.get(
        "http://127.0.0.1:9123/elgato/accessory-info",
        text=load_fixture("elgato/info.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        "http://127.0.0.2:9123/elgato/accessory-info",
        text=load_fixture("elgato/info.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    settings = "elgato/settings.json"
    if color:
        settings = "elgato/settings-color.json"

    aioclient_mock.get(
        "http://127.0.0.1:9123/elgato/lights/settings",
        text=load_fixture(settings),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    state = "elgato/state.json"
    if mode_color:
        state = "elgato/state-color.json"

    aioclient_mock.get(
        "http://127.0.0.1:9123/elgato/lights",
        text=load_fixture(state),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.put(
        "http://127.0.0.1:9123/elgato/lights",
        text=load_fixture("elgato/state.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="CN11A1A00001",
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 9123,
            CONF_SERIAL_NUMBER: "CN11A1A00001",
        },
    )

    entry.add_to_hass(hass)

    if not skip_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
