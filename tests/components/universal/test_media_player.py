"""The tests for the Universal Media player platform."""
import asyncio
from copy import copy
import unittest
from unittest.mock import patch

from voluptuous.error import MultipleInvalid

from homeassistant import config as hass_config
import homeassistant.components.input_number as input_number
import homeassistant.components.input_select as input_select
import homeassistant.components.media_player as media_player
import homeassistant.components.switch as switch
import homeassistant.components.universal.media_player as universal
from homeassistant.const import (
    SERVICE_RELOAD,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNKNOWN,
)
from homeassistant.core import Context, callback
from homeassistant.setup import async_setup_component, setup_component

from tests.common import get_fixture_path, get_test_home_assistant, mock_service


def validate_config(config):
    """Use the platform schema to validate configuration."""
    validated_config = universal.PLATFORM_SCHEMA(config)
    validated_config.pop("platform")
    return validated_config


class MockMediaPlayer(media_player.MediaPlayerEntity):
    """Mock media player for testing."""

    def __init__(self, hass, name):
        """Initialize the media player."""
        self.hass = hass
        self._name = name
        self.entity_id = media_player.ENTITY_ID_FORMAT.format(name)
        self._state = STATE_OFF
        self._volume_level = 0
        self._is_volume_muted = False
        self._media_title = None
        self._supported_features = 0
        self._source = None
        self._tracks = 12
        self._media_image_url = None
        self._shuffle = False
        self._sound_mode = None

        self.service_calls = {
            "turn_on": mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_TURN_ON
            ),
            "turn_off": mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_TURN_OFF
            ),
            "mute_volume": mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_VOLUME_MUTE
            ),
            "set_volume_level": mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_VOLUME_SET
            ),
            "media_play": mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_MEDIA_PLAY
            ),
            "media_pause": mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_MEDIA_PAUSE
            ),
            "media_stop": mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_MEDIA_STOP
            ),
            "media_previous_track": mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_MEDIA_PREVIOUS_TRACK
            ),
            "media_next_track": mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_MEDIA_NEXT_TRACK
            ),
            "media_seek": mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_MEDIA_SEEK
            ),
            "play_media": mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_PLAY_MEDIA
            ),
            "volume_up": mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_VOLUME_UP
            ),
            "volume_down": mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_VOLUME_DOWN
            ),
            "media_play_pause": mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_MEDIA_PLAY_PAUSE
            ),
            "select_sound_mode": mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_SELECT_SOUND_MODE
            ),
            "select_source": mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_SELECT_SOURCE
            ),
            "toggle": mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_TOGGLE
            ),
            "clear_playlist": mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_CLEAR_PLAYLIST
            ),
            "repeat_set": mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_REPEAT_SET
            ),
            "shuffle_set": mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_SHUFFLE_SET
            ),
        }

    @property
    def name(self):
        """Return the name of player."""
        return self._name

    @property
    def state(self):
        """Return the state of the player."""
        return self._state

    @property
    def volume_level(self):
        """Return the volume level of player."""
        return self._volume_level

    @property
    def is_volume_muted(self):
        """Return true if the media player is muted."""
        return self._is_volume_muted

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return self._supported_features

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        return self._media_image_url

    @property
    def shuffle(self):
        """Return true if the media player is shuffling."""
        return self._shuffle

    def turn_on(self):
        """Mock turn_on function."""
        self._state = None

    def turn_off(self):
        """Mock turn_off function."""
        self._state = STATE_OFF

    def mute_volume(self, mute):
        """Mock mute function."""
        self._is_volume_muted = mute

    def set_volume_level(self, volume):
        """Mock set volume level."""
        self._volume_level = volume

    def media_play(self):
        """Mock play."""
        self._state = STATE_PLAYING

    def media_pause(self):
        """Mock pause."""
        self._state = STATE_PAUSED

    def select_sound_mode(self, sound_mode):
        """Set the sound mode."""
        self._sound_mode = sound_mode

    def select_source(self, source):
        """Set the input source."""
        self._source = source

    def async_toggle(self):
        """Toggle the power on the media player."""
        self._state = STATE_OFF if self._state == STATE_ON else STATE_ON

    def clear_playlist(self):
        """Clear players playlist."""
        self._tracks = 0

    def set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        self._shuffle = shuffle

    def set_repeat(self, repeat):
        """Enable/disable repeat mode."""
        self._repeat = repeat


class TestMediaPlayer(unittest.TestCase):
    """Test the media_player module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        self.mock_mp_1 = MockMediaPlayer(self.hass, "mock1")
        self.mock_mp_1.schedule_update_ha_state()

        self.mock_mp_2 = MockMediaPlayer(self.hass, "mock2")
        self.mock_mp_2.schedule_update_ha_state()

        self.hass.block_till_done()

        self.mock_mute_switch_id = switch.ENTITY_ID_FORMAT.format("mute")
        self.hass.states.set(self.mock_mute_switch_id, STATE_OFF)

        self.mock_state_switch_id = switch.ENTITY_ID_FORMAT.format("state")
        self.hass.states.set(self.mock_state_switch_id, STATE_OFF)

        self.mock_volume_id = f"{input_number.DOMAIN}.volume_level"
        self.hass.states.set(self.mock_volume_id, 0)

        self.mock_source_list_id = f"{input_select.DOMAIN}.source_list"
        self.hass.states.set(self.mock_source_list_id, ["dvd", "htpc"])

        self.mock_source_id = f"{input_select.DOMAIN}.source"
        self.hass.states.set(self.mock_source_id, "dvd")

        self.mock_sound_mode_list_id = f"{input_select.DOMAIN}.sound_mode_list"
        self.hass.states.set(self.mock_sound_mode_list_id, ["music", "movie"])

        self.mock_sound_mode_id = f"{input_select.DOMAIN}.sound_mode"
        self.hass.states.set(self.mock_sound_mode_id, "music")

        self.mock_shuffle_switch_id = switch.ENTITY_ID_FORMAT.format("shuffle")
        self.hass.states.set(self.mock_shuffle_switch_id, STATE_OFF)

        self.mock_repeat_switch_id = switch.ENTITY_ID_FORMAT.format("repeat")
        self.hass.states.set(self.mock_repeat_switch_id, STATE_OFF)

        self.config_children_only = {
            "name": "test",
            "platform": "universal",
            "children": [
                media_player.ENTITY_ID_FORMAT.format("mock1"),
                media_player.ENTITY_ID_FORMAT.format("mock2"),
            ],
        }
        self.config_children_and_attr = {
            "name": "test",
            "platform": "universal",
            "children": [
                media_player.ENTITY_ID_FORMAT.format("mock1"),
                media_player.ENTITY_ID_FORMAT.format("mock2"),
            ],
            "attributes": {
                "is_volume_muted": self.mock_mute_switch_id,
                "volume_level": self.mock_volume_id,
                "source": self.mock_source_id,
                "source_list": self.mock_source_list_id,
                "state": self.mock_state_switch_id,
                "shuffle": self.mock_shuffle_switch_id,
                "repeat": self.mock_repeat_switch_id,
                "sound_mode_list": self.mock_sound_mode_list_id,
                "sound_mode": self.mock_sound_mode_id,
            },
        }
        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_config_children_only(self):
        """Check config with only children."""
        config_start = copy(self.config_children_only)
        del config_start["platform"]
        config_start["commands"] = {}
        config_start["attributes"] = {}

        config = validate_config(self.config_children_only)
        assert config_start == config

    def test_config_children_and_attr(self):
        """Check config with children and attributes."""
        config_start = copy(self.config_children_and_attr)
        del config_start["platform"]
        config_start["commands"] = {}

        config = validate_config(self.config_children_and_attr)
        assert config_start == config

    def test_config_no_name(self):
        """Check config with no Name entry."""
        response = True
        try:
            validate_config({"platform": "universal"})
        except MultipleInvalid:
            response = False
        assert not response

    def test_config_bad_children(self):
        """Check config with bad children entry."""
        config_no_children = {"name": "test", "platform": "universal"}
        config_bad_children = {"name": "test", "children": {}, "platform": "universal"}

        config_no_children = validate_config(config_no_children)
        assert [] == config_no_children["children"]

        config_bad_children = validate_config(config_bad_children)
        assert [] == config_bad_children["children"]

    def test_config_bad_commands(self):
        """Check config with bad commands entry."""
        config = {"name": "test", "platform": "universal"}

        config = validate_config(config)
        assert {} == config["commands"]

    def test_config_bad_attributes(self):
        """Check config with bad attributes."""
        config = {"name": "test", "platform": "universal"}

        config = validate_config(config)
        assert {} == config["attributes"]

    def test_config_bad_key(self):
        """Check config with bad key."""
        config = {"name": "test", "asdf": 5, "platform": "universal"}

        config = validate_config(config)
        assert "asdf" not in config

    def test_platform_setup(self):
        """Test platform setup."""
        config = {"name": "test", "platform": "universal"}
        bad_config = {"platform": "universal"}
        entities = []

        def add_entities(new_entities):
            """Add devices to list."""
            for dev in new_entities:
                entities.append(dev)

        setup_ok = True
        try:
            asyncio.run_coroutine_threadsafe(
                universal.async_setup_platform(
                    self.hass, validate_config(bad_config), add_entities
                ),
                self.hass.loop,
            ).result()
        except MultipleInvalid:
            setup_ok = False
        assert not setup_ok
        assert len(entities) == 0

        asyncio.run_coroutine_threadsafe(
            universal.async_setup_platform(
                self.hass, validate_config(config), add_entities
            ),
            self.hass.loop,
        ).result()
        assert len(entities) == 1
        assert entities[0].name == "test"

    def test_master_state(self):
        """Test master state property."""
        config = validate_config(self.config_children_only)

        ump = universal.UniversalMediaPlayer(self.hass, **config)

        assert ump.master_state is None

    def test_master_state_with_attrs(self):
        """Test master state property."""
        config = validate_config(self.config_children_and_attr)

        ump = universal.UniversalMediaPlayer(self.hass, **config)

        assert ump.master_state == STATE_OFF
        self.hass.states.set(self.mock_state_switch_id, STATE_ON)
        assert ump.master_state == STATE_ON

    def test_master_state_with_bad_attrs(self):
        """Test master state property."""
        config = copy(self.config_children_and_attr)
        config["attributes"]["state"] = "bad.entity_id"
        config = validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)

        assert ump.master_state == STATE_OFF

    def test_active_child_state(self):
        """Test active child state property."""
        config = validate_config(self.config_children_only)

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config["name"])
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        assert ump._child_state is None

        self.mock_mp_1._state = STATE_PLAYING
        self.mock_mp_1.schedule_update_ha_state()
        self.hass.block_till_done()
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()
        assert self.mock_mp_1.entity_id == ump._child_state.entity_id

        self.mock_mp_2._state = STATE_PLAYING
        self.mock_mp_2.schedule_update_ha_state()
        self.hass.block_till_done()
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()
        assert self.mock_mp_1.entity_id == ump._child_state.entity_id

        self.mock_mp_1._state = STATE_OFF
        self.mock_mp_1.schedule_update_ha_state()
        self.hass.block_till_done()
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()
        assert self.mock_mp_2.entity_id == ump._child_state.entity_id

    def test_name(self):
        """Test name property."""
        config = validate_config(self.config_children_only)

        ump = universal.UniversalMediaPlayer(self.hass, **config)

        assert config["name"] == ump.name

    def test_polling(self):
        """Test should_poll property."""
        config = validate_config(self.config_children_only)

        ump = universal.UniversalMediaPlayer(self.hass, **config)

        assert ump.should_poll is False

    def test_state_children_only(self):
        """Test media player state with only children."""
        config = validate_config(self.config_children_only)

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config["name"])
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        assert ump.state, STATE_OFF

        self.mock_mp_1._state = STATE_PLAYING
        self.mock_mp_1.schedule_update_ha_state()
        self.hass.block_till_done()
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()
        assert ump.state == STATE_PLAYING

    def test_state_with_children_and_attrs(self):
        """Test media player with children and master state."""
        config = validate_config(self.config_children_and_attr)

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config["name"])
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        assert ump.state == STATE_OFF

        self.hass.states.set(self.mock_state_switch_id, STATE_ON)
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()
        assert ump.state == STATE_ON

        self.mock_mp_1._state = STATE_PLAYING
        self.mock_mp_1.schedule_update_ha_state()
        self.hass.block_till_done()
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()
        assert ump.state == STATE_PLAYING

        self.hass.states.set(self.mock_state_switch_id, STATE_OFF)
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()
        assert ump.state == STATE_OFF

    def test_volume_level(self):
        """Test volume level property."""
        config = validate_config(self.config_children_only)

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config["name"])
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        assert ump.volume_level is None

        self.mock_mp_1._state = STATE_PLAYING
        self.mock_mp_1.schedule_update_ha_state()
        self.hass.block_till_done()
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()
        assert ump.volume_level == 0

        self.mock_mp_1._volume_level = 1
        self.mock_mp_1.schedule_update_ha_state()
        self.hass.block_till_done()
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()
        assert ump.volume_level == 1

    def test_media_image_url(self):
        """Test media_image_url property."""
        test_url = "test_url"
        config = validate_config(self.config_children_only)

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config["name"])
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        assert ump.media_image_url is None

        self.mock_mp_1._state = STATE_PLAYING
        self.mock_mp_1._media_image_url = test_url
        self.mock_mp_1.schedule_update_ha_state()
        self.hass.block_till_done()
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()
        # mock_mp_1 will convert the url to the api proxy url. This test
        # ensures ump passes through the same url without an additional proxy.
        assert self.mock_mp_1.entity_picture == ump.entity_picture

    def test_is_volume_muted_children_only(self):
        """Test is volume muted property w/ children only."""
        config = validate_config(self.config_children_only)

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config["name"])
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        assert not ump.is_volume_muted

        self.mock_mp_1._state = STATE_PLAYING
        self.mock_mp_1.schedule_update_ha_state()
        self.hass.block_till_done()
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()
        assert not ump.is_volume_muted

        self.mock_mp_1._is_volume_muted = True
        self.mock_mp_1.schedule_update_ha_state()
        self.hass.block_till_done()
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()
        assert ump.is_volume_muted

    def test_sound_mode_list_children_and_attr(self):
        """Test sound mode list property w/ children and attrs."""
        config = validate_config(self.config_children_and_attr)

        ump = universal.UniversalMediaPlayer(self.hass, **config)

        assert ump.sound_mode_list == "['music', 'movie']"

        self.hass.states.set(self.mock_sound_mode_list_id, ["music", "movie", "game"])
        assert ump.sound_mode_list == "['music', 'movie', 'game']"

    def test_source_list_children_and_attr(self):
        """Test source list property w/ children and attrs."""
        config = validate_config(self.config_children_and_attr)

        ump = universal.UniversalMediaPlayer(self.hass, **config)

        assert ump.source_list == "['dvd', 'htpc']"

        self.hass.states.set(self.mock_source_list_id, ["dvd", "htpc", "game"])
        assert ump.source_list == "['dvd', 'htpc', 'game']"

    def test_sound_mode_children_and_attr(self):
        """Test sound modeproperty w/ children and attrs."""
        config = validate_config(self.config_children_and_attr)

        ump = universal.UniversalMediaPlayer(self.hass, **config)

        assert ump.sound_mode == "music"

        self.hass.states.set(self.mock_sound_mode_id, "movie")
        assert ump.sound_mode == "movie"

    def test_source_children_and_attr(self):
        """Test source property w/ children and attrs."""
        config = validate_config(self.config_children_and_attr)

        ump = universal.UniversalMediaPlayer(self.hass, **config)

        assert ump.source == "dvd"

        self.hass.states.set(self.mock_source_id, "htpc")
        assert ump.source == "htpc"

    def test_volume_level_children_and_attr(self):
        """Test volume level property w/ children and attrs."""
        config = validate_config(self.config_children_and_attr)

        ump = universal.UniversalMediaPlayer(self.hass, **config)

        assert ump.volume_level == 0

        self.hass.states.set(self.mock_volume_id, 100)
        assert ump.volume_level == 100

    def test_is_volume_muted_children_and_attr(self):
        """Test is volume muted property w/ children and attrs."""
        config = validate_config(self.config_children_and_attr)

        ump = universal.UniversalMediaPlayer(self.hass, **config)

        assert not ump.is_volume_muted

        self.hass.states.set(self.mock_mute_switch_id, STATE_ON)
        assert ump.is_volume_muted

    def test_supported_features_children_only(self):
        """Test supported media commands with only children."""
        config = validate_config(self.config_children_only)

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config["name"])
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        assert ump.supported_features == 0

        self.mock_mp_1._supported_features = 512
        self.mock_mp_1._state = STATE_PLAYING
        self.mock_mp_1.schedule_update_ha_state()
        self.hass.block_till_done()
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()
        assert ump.supported_features == 512

    def test_supported_features_children_and_cmds(self):
        """Test supported media commands with children and attrs."""
        config = copy(self.config_children_and_attr)
        excmd = {"service": "media_player.test", "data": {}}
        config["commands"] = {
            "turn_on": excmd,
            "turn_off": excmd,
            "volume_up": excmd,
            "volume_down": excmd,
            "volume_mute": excmd,
            "volume_set": excmd,
            "select_sound_mode": excmd,
            "select_source": excmd,
            "repeat_set": excmd,
            "shuffle_set": excmd,
            "media_play": excmd,
            "media_pause": excmd,
            "media_stop": excmd,
            "media_next_track": excmd,
            "media_previous_track": excmd,
            "toggle": excmd,
            "play_media": excmd,
            "clear_playlist": excmd,
        }
        config = validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config["name"])
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        self.mock_mp_1._state = STATE_PLAYING
        self.mock_mp_1.schedule_update_ha_state()
        self.hass.block_till_done()
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        check_flags = (
            universal.SUPPORT_TURN_ON
            | universal.SUPPORT_TURN_OFF
            | universal.SUPPORT_VOLUME_STEP
            | universal.SUPPORT_VOLUME_MUTE
            | universal.SUPPORT_SELECT_SOUND_MODE
            | universal.SUPPORT_SELECT_SOURCE
            | universal.SUPPORT_REPEAT_SET
            | universal.SUPPORT_SHUFFLE_SET
            | universal.SUPPORT_VOLUME_SET
            | universal.SUPPORT_PLAY
            | universal.SUPPORT_PAUSE
            | universal.SUPPORT_STOP
            | universal.SUPPORT_NEXT_TRACK
            | universal.SUPPORT_PREVIOUS_TRACK
            | universal.SUPPORT_PLAY_MEDIA
            | universal.SUPPORT_CLEAR_PLAYLIST
        )

        assert check_flags == ump.supported_features

    def test_overrides(self):
        """Test overrides."""
        config = copy(self.config_children_and_attr)
        excmd = {"service": "test.override", "data": {}}
        config["name"] = "overridden"
        config["commands"] = {
            "turn_on": excmd,
            "turn_off": excmd,
            "volume_up": excmd,
            "volume_down": excmd,
            "volume_mute": excmd,
            "volume_set": excmd,
            "select_sound_mode": excmd,
            "select_source": excmd,
            "repeat_set": excmd,
            "shuffle_set": excmd,
            "media_play": excmd,
            "media_play_pause": excmd,
            "media_pause": excmd,
            "media_stop": excmd,
            "media_next_track": excmd,
            "media_previous_track": excmd,
            "clear_playlist": excmd,
            "play_media": excmd,
            "toggle": excmd,
        }
        setup_component(self.hass, "media_player", {"media_player": config})

        service = mock_service(self.hass, "test", "override")
        self.hass.services.call(
            "media_player",
            "turn_on",
            service_data={"entity_id": "media_player.overridden"},
            blocking=True,
        )
        assert len(service) == 1
        self.hass.services.call(
            "media_player",
            "turn_off",
            service_data={"entity_id": "media_player.overridden"},
            blocking=True,
        )
        assert len(service) == 2
        self.hass.services.call(
            "media_player",
            "volume_up",
            service_data={"entity_id": "media_player.overridden"},
            blocking=True,
        )
        assert len(service) == 3
        self.hass.services.call(
            "media_player",
            "volume_down",
            service_data={"entity_id": "media_player.overridden"},
            blocking=True,
        )
        assert len(service) == 4
        self.hass.services.call(
            "media_player",
            "volume_mute",
            service_data={
                "entity_id": "media_player.overridden",
                "is_volume_muted": True,
            },
            blocking=True,
        )
        assert len(service) == 5
        self.hass.services.call(
            "media_player",
            "volume_set",
            service_data={"entity_id": "media_player.overridden", "volume_level": 1},
            blocking=True,
        )
        assert len(service) == 6
        self.hass.services.call(
            "media_player",
            "select_sound_mode",
            service_data={
                "entity_id": "media_player.overridden",
                "sound_mode": "music",
            },
            blocking=True,
        )
        assert len(service) == 7
        self.hass.services.call(
            "media_player",
            "select_source",
            service_data={"entity_id": "media_player.overridden", "source": "video1"},
            blocking=True,
        )
        assert len(service) == 8
        self.hass.services.call(
            "media_player",
            "repeat_set",
            service_data={"entity_id": "media_player.overridden", "repeat": "all"},
            blocking=True,
        )
        assert len(service) == 9
        self.hass.services.call(
            "media_player",
            "shuffle_set",
            service_data={"entity_id": "media_player.overridden", "shuffle": True},
            blocking=True,
        )
        assert len(service) == 10
        self.hass.services.call(
            "media_player",
            "media_play",
            service_data={"entity_id": "media_player.overridden"},
            blocking=True,
        )
        assert len(service) == 11
        self.hass.services.call(
            "media_player",
            "media_pause",
            service_data={"entity_id": "media_player.overridden"},
            blocking=True,
        )
        assert len(service) == 12
        self.hass.services.call(
            "media_player",
            "media_stop",
            service_data={"entity_id": "media_player.overridden"},
            blocking=True,
        )
        assert len(service) == 13
        self.hass.services.call(
            "media_player",
            "media_next_track",
            service_data={"entity_id": "media_player.overridden"},
            blocking=True,
        )
        assert len(service) == 14
        self.hass.services.call(
            "media_player",
            "media_previous_track",
            service_data={"entity_id": "media_player.overridden"},
            blocking=True,
        )
        assert len(service) == 15
        self.hass.services.call(
            "media_player",
            "clear_playlist",
            service_data={"entity_id": "media_player.overridden"},
            blocking=True,
        )
        assert len(service) == 16
        self.hass.services.call(
            "media_player",
            "media_play_pause",
            service_data={"entity_id": "media_player.overridden"},
            blocking=True,
        )
        assert len(service) == 17
        self.hass.services.call(
            "media_player",
            "play_media",
            service_data={
                "entity_id": "media_player.overridden",
                "media_content_id": 1,
                "media_content_type": "channel",
            },
            blocking=True,
        )
        assert len(service) == 18
        self.hass.services.call(
            "media_player",
            "toggle",
            service_data={"entity_id": "media_player.overridden"},
            blocking=True,
        )
        assert len(service) == 19

    def test_supported_features_play_pause(self):
        """Test supported media commands with play_pause function."""
        config = copy(self.config_children_and_attr)
        excmd = {"service": "media_player.test", "data": {"entity_id": "test"}}
        config["commands"] = {"media_play_pause": excmd}
        config = validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config["name"])
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        self.mock_mp_1._state = STATE_PLAYING
        self.mock_mp_1.schedule_update_ha_state()
        self.hass.block_till_done()
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        check_flags = universal.SUPPORT_PLAY | universal.SUPPORT_PAUSE

        assert check_flags == ump.supported_features

    def test_service_call_no_active_child(self):
        """Test a service call to children with no active child."""
        config = validate_config(self.config_children_and_attr)

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config["name"])
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        self.mock_mp_1._state = STATE_OFF
        self.mock_mp_1.schedule_update_ha_state()
        self.mock_mp_2._state = STATE_OFF
        self.mock_mp_2.schedule_update_ha_state()
        self.hass.block_till_done()
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        asyncio.run_coroutine_threadsafe(ump.async_turn_off(), self.hass.loop).result()
        assert len(self.mock_mp_1.service_calls["turn_off"]) == 0
        assert len(self.mock_mp_2.service_calls["turn_off"]) == 0

    def test_service_call_to_child(self):
        """Test service calls that should be routed to a child."""
        config = validate_config(self.config_children_only)

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config["name"])
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        self.mock_mp_2._state = STATE_PLAYING
        self.mock_mp_2.schedule_update_ha_state()
        self.hass.block_till_done()
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        asyncio.run_coroutine_threadsafe(ump.async_turn_off(), self.hass.loop).result()
        assert len(self.mock_mp_2.service_calls["turn_off"]) == 1

        asyncio.run_coroutine_threadsafe(ump.async_turn_on(), self.hass.loop).result()
        assert len(self.mock_mp_2.service_calls["turn_on"]) == 1

        asyncio.run_coroutine_threadsafe(
            ump.async_mute_volume(True), self.hass.loop
        ).result()
        assert len(self.mock_mp_2.service_calls["mute_volume"]) == 1

        asyncio.run_coroutine_threadsafe(
            ump.async_set_volume_level(0.5), self.hass.loop
        ).result()
        assert len(self.mock_mp_2.service_calls["set_volume_level"]) == 1

        asyncio.run_coroutine_threadsafe(
            ump.async_media_play(), self.hass.loop
        ).result()
        assert len(self.mock_mp_2.service_calls["media_play"]) == 1

        asyncio.run_coroutine_threadsafe(
            ump.async_media_pause(), self.hass.loop
        ).result()
        assert len(self.mock_mp_2.service_calls["media_pause"]) == 1

        asyncio.run_coroutine_threadsafe(
            ump.async_media_stop(), self.hass.loop
        ).result()
        assert len(self.mock_mp_2.service_calls["media_stop"]) == 1

        asyncio.run_coroutine_threadsafe(
            ump.async_media_previous_track(), self.hass.loop
        ).result()
        assert len(self.mock_mp_2.service_calls["media_previous_track"]) == 1

        asyncio.run_coroutine_threadsafe(
            ump.async_media_next_track(), self.hass.loop
        ).result()
        assert len(self.mock_mp_2.service_calls["media_next_track"]) == 1

        asyncio.run_coroutine_threadsafe(
            ump.async_media_seek(100), self.hass.loop
        ).result()
        assert len(self.mock_mp_2.service_calls["media_seek"]) == 1

        asyncio.run_coroutine_threadsafe(
            ump.async_play_media("movie", "batman"), self.hass.loop
        ).result()
        assert len(self.mock_mp_2.service_calls["play_media"]) == 1

        asyncio.run_coroutine_threadsafe(ump.async_volume_up(), self.hass.loop).result()
        assert len(self.mock_mp_2.service_calls["volume_up"]) == 1

        asyncio.run_coroutine_threadsafe(
            ump.async_volume_down(), self.hass.loop
        ).result()
        assert len(self.mock_mp_2.service_calls["volume_down"]) == 1

        asyncio.run_coroutine_threadsafe(
            ump.async_media_play_pause(), self.hass.loop
        ).result()
        assert len(self.mock_mp_2.service_calls["media_play_pause"]) == 1

        asyncio.run_coroutine_threadsafe(
            ump.async_select_sound_mode("music"), self.hass.loop
        ).result()
        assert len(self.mock_mp_2.service_calls["select_sound_mode"]) == 1

        asyncio.run_coroutine_threadsafe(
            ump.async_select_source("dvd"), self.hass.loop
        ).result()
        assert len(self.mock_mp_2.service_calls["select_source"]) == 1

        asyncio.run_coroutine_threadsafe(
            ump.async_clear_playlist(), self.hass.loop
        ).result()
        assert len(self.mock_mp_2.service_calls["clear_playlist"]) == 1

        asyncio.run_coroutine_threadsafe(
            ump.async_set_repeat(True), self.hass.loop
        ).result()
        assert len(self.mock_mp_2.service_calls["repeat_set"]) == 1

        asyncio.run_coroutine_threadsafe(
            ump.async_set_shuffle(True), self.hass.loop
        ).result()
        assert len(self.mock_mp_2.service_calls["shuffle_set"]) == 1

        asyncio.run_coroutine_threadsafe(ump.async_toggle(), self.hass.loop).result()
        # Delegate to turn_off
        assert len(self.mock_mp_2.service_calls["turn_off"]) == 2

    def test_service_call_to_command(self):
        """Test service call to command."""
        config = copy(self.config_children_only)
        config["commands"] = {"turn_off": {"service": "test.turn_off", "data": {}}}
        config = validate_config(config)

        service = mock_service(self.hass, "test", "turn_off")

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config["name"])
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        self.mock_mp_2._state = STATE_PLAYING
        self.mock_mp_2.schedule_update_ha_state()
        self.hass.block_till_done()
        asyncio.run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        asyncio.run_coroutine_threadsafe(ump.async_turn_off(), self.hass.loop).result()
        assert len(service) == 1


async def test_state_template(hass):
    """Test with a simple valid state template."""
    hass.states.async_set("sensor.test_sensor", STATE_ON)

    await async_setup_component(
        hass,
        "media_player",
        {
            "media_player": {
                "platform": "universal",
                "name": "tv",
                "state_template": "{{ states.sensor.test_sensor.state }}",
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 2
    await hass.async_start()

    await hass.async_block_till_done()
    assert hass.states.get("media_player.tv").state == STATE_ON
    hass.states.async_set("sensor.test_sensor", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get("media_player.tv").state == STATE_OFF


async def test_device_class(hass):
    """Test device_class property."""
    hass.states.async_set("sensor.test_sensor", "on")

    await async_setup_component(
        hass,
        "media_player",
        {
            "media_player": {
                "platform": "universal",
                "name": "tv",
                "device_class": "tv",
            }
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get("media_player.tv").attributes["device_class"] == "tv"


async def test_invalid_state_template(hass):
    """Test invalid state template sets state to None."""
    hass.states.async_set("sensor.test_sensor", "on")

    await async_setup_component(
        hass,
        "media_player",
        {
            "media_player": {
                "platform": "universal",
                "name": "tv",
                "state_template": "{{ states.sensor.test_sensor.state + x }}",
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 2
    await hass.async_start()

    await hass.async_block_till_done()
    assert hass.states.get("media_player.tv").state == STATE_UNKNOWN
    hass.states.async_set("sensor.test_sensor", "off")
    await hass.async_block_till_done()
    assert hass.states.get("media_player.tv").state == STATE_UNKNOWN


async def test_master_state_with_template(hass):
    """Test the state_template option."""
    hass.states.async_set("input_boolean.test", STATE_OFF)
    hass.states.async_set("media_player.mock1", STATE_OFF)

    templ = (
        '{% if states.input_boolean.test.state == "off" %}on'
        "{% else %}{{ states.media_player.mock1.state }}{% endif %}"
    )

    await async_setup_component(
        hass,
        "media_player",
        {
            "media_player": {
                "platform": "universal",
                "name": "tv",
                "state_template": templ,
            }
        },
    )

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 3
    await hass.async_start()

    await hass.async_block_till_done()
    assert hass.states.get("media_player.tv").state == STATE_ON

    events = []

    hass.helpers.event.async_track_state_change_event(
        "media_player.tv", callback(lambda event: events.append(event))
    )

    context = Context()
    hass.states.async_set("input_boolean.test", STATE_ON, context=context)
    await hass.async_block_till_done()

    assert hass.states.get("media_player.tv").state == STATE_OFF
    assert events[0].context == context


async def test_reload(hass):
    """Test reloading the media player from yaml."""
    hass.states.async_set("input_boolean.test", STATE_OFF)
    hass.states.async_set("media_player.mock1", STATE_OFF)

    templ = (
        '{% if states.input_boolean.test.state == "off" %}on'
        "{% else %}{{ states.media_player.mock1.state }}{% endif %}"
    )

    await async_setup_component(
        hass,
        "media_player",
        {
            "media_player": {
                "platform": "universal",
                "name": "tv",
                "state_template": templ,
            }
        },
    )

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 3
    await hass.async_start()

    await hass.async_block_till_done()
    assert hass.states.get("media_player.tv").state == STATE_ON

    hass.states.async_set("input_boolean.test", STATE_ON)
    await hass.async_block_till_done()

    assert hass.states.get("media_player.tv").state == STATE_OFF

    hass.states.async_set("media_player.master_bedroom_2", STATE_OFF)
    hass.states.async_set(
        "remote.alexander_master_bedroom",
        STATE_ON,
        {"activity_list": ["act1", "act2"], "current_activity": "act2"},
    )

    yaml_path = get_fixture_path("configuration.yaml", "universal")
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            "universal",
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 5

    assert hass.states.get("media_player.tv") is None
    assert hass.states.get("media_player.master_bed_tv").state == "on"
    assert hass.states.get("media_player.master_bed_tv").attributes["source"] == "act2"
    assert (
        "device_class" not in hass.states.get("media_player.master_bed_tv").attributes
    )
