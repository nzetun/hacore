"""The tests for the MaryTTS speech platform."""
import asyncio
import os
import shutil
from unittest.mock import patch

from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
)
import homeassistant.components.tts as tts
from homeassistant.config import async_process_ha_core_config
from homeassistant.setup import setup_component

from tests.common import assert_setup_component, get_test_home_assistant, mock_service


class TestTTSMaryTTSPlatform:
    """Test the speech component."""

    def setup_method(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        asyncio.run_coroutine_threadsafe(
            async_process_ha_core_config(
                self.hass, {"internal_url": "http://example.local:8123"}
            ),
            self.hass.loop,
        )

        self.host = "localhost"
        self.port = 59125
        self.params = {
            "INPUT_TEXT": "HomeAssistant",
            "INPUT_TYPE": "TEXT",
            "OUTPUT_TYPE": "AUDIO",
            "LOCALE": "en_US",
            "AUDIO": "WAVE_FILE",
            "VOICE": "cmu-slt-hsmm",
        }

    def teardown_method(self):
        """Stop everything that was started."""
        default_tts = self.hass.config.path(tts.DEFAULT_CACHE_DIR)
        if os.path.isdir(default_tts):
            shutil.rmtree(default_tts)

        self.hass.stop()

    def test_setup_component(self):
        """Test setup component."""
        config = {tts.DOMAIN: {"platform": "marytts"}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

    def test_service_say(self):
        """Test service call say."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        config = {tts.DOMAIN: {"platform": "marytts"}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        with patch(
            "homeassistant.components.marytts.tts.MaryTTS.speak",
            return_value=b"audio",
        ) as mock_speak:
            self.hass.services.call(
                tts.DOMAIN,
                "marytts_say",
                {
                    "entity_id": "media_player.something",
                    tts.ATTR_MESSAGE: "HomeAssistant",
                },
            )
            self.hass.block_till_done()

        mock_speak.assert_called_once()
        mock_speak.assert_called_with("HomeAssistant", {})

        assert len(calls) == 1
        assert calls[0].data[ATTR_MEDIA_CONTENT_ID].find(".wav") != -1

    def test_service_say_with_effect(self):
        """Test service call say with effects."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        config = {
            tts.DOMAIN: {"platform": "marytts", "effect": {"Volume": "amount:2.0;"}}
        }

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        with patch(
            "homeassistant.components.marytts.tts.MaryTTS.speak",
            return_value=b"audio",
        ) as mock_speak:
            self.hass.services.call(
                tts.DOMAIN,
                "marytts_say",
                {
                    "entity_id": "media_player.something",
                    tts.ATTR_MESSAGE: "HomeAssistant",
                },
            )
            self.hass.block_till_done()

        mock_speak.assert_called_once()
        mock_speak.assert_called_with("HomeAssistant", {"Volume": "amount:2.0;"})

        assert len(calls) == 1
        assert calls[0].data[ATTR_MEDIA_CONTENT_ID].find(".wav") != -1

    def test_service_say_http_error(self):
        """Test service call say."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        config = {tts.DOMAIN: {"platform": "marytts"}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        with patch(
            "homeassistant.components.marytts.tts.MaryTTS.speak",
            side_effect=Exception(),
        ) as mock_speak:
            self.hass.services.call(
                tts.DOMAIN,
                "marytts_say",
                {
                    "entity_id": "media_player.something",
                    tts.ATTR_MESSAGE: "HomeAssistant",
                },
            )
            self.hass.block_till_done()

        mock_speak.assert_called_once()
        assert len(calls) == 0
