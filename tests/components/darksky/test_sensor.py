"""The tests for the Dark Sky platform."""
from datetime import timedelta
import re
import unittest
from unittest.mock import MagicMock, patch

import forecastio
from requests.exceptions import HTTPError
import requests_mock

from homeassistant.components.darksky import sensor as darksky
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant, load_fixture

VALID_CONFIG_MINIMAL = {
    "sensor": {
        "platform": "darksky",
        "api_key": "foo",
        "forecast": [1, 2],
        "hourly_forecast": [1, 2],
        "monitored_conditions": ["summary", "icon", "temperature_high", "alerts"],
        "scan_interval": timedelta(seconds=120),
    }
}

INVALID_CONFIG_MINIMAL = {
    "sensor": {
        "platform": "darksky",
        "api_key": "foo",
        "forecast": [1, 2],
        "hourly_forecast": [1, 2],
        "monitored_conditions": ["summary", "iocn", "temperature_high"],
        "scan_interval": timedelta(seconds=120),
    }
}

VALID_CONFIG_LANG_DE = {
    "sensor": {
        "platform": "darksky",
        "api_key": "foo",
        "forecast": [1, 2],
        "hourly_forecast": [1, 2],
        "units": "us",
        "language": "de",
        "monitored_conditions": [
            "summary",
            "icon",
            "temperature_high",
            "minutely_summary",
            "hourly_summary",
            "daily_summary",
            "humidity",
            "alerts",
        ],
        "scan_interval": timedelta(seconds=120),
    }
}

INVALID_CONFIG_LANG = {
    "sensor": {
        "platform": "darksky",
        "api_key": "foo",
        "forecast": [1, 2],
        "hourly_forecast": [1, 2],
        "language": "yz",
        "monitored_conditions": ["summary", "icon", "temperature_high"],
        "scan_interval": timedelta(seconds=120),
    }
}

VALID_CONFIG_ALERTS = {
    "sensor": {
        "platform": "darksky",
        "api_key": "foo",
        "forecast": [1, 2],
        "hourly_forecast": [1, 2],
        "monitored_conditions": ["summary", "icon", "temperature_high", "alerts"],
        "scan_interval": timedelta(seconds=120),
    }
}


def load_forecastMock(key, lat, lon, units, lang):  # pylint: disable=invalid-name
    """Mock darksky forecast loading."""
    return ""


class TestDarkSkySetup(unittest.TestCase):
    """Test the Dark Sky platform."""

    def add_entities(self, new_entities, update_before_add=False):
        """Mock add entities."""
        if update_before_add:
            for entity in new_entities:
                entity.update()

        for entity in new_entities:
            self.entities.append(entity)

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.key = "foo"
        self.lat = self.hass.config.latitude = 37.8267
        self.lon = self.hass.config.longitude = -122.423
        self.entities = []
        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch(
        "homeassistant.components.darksky.sensor.forecastio.load_forecast",
        new=load_forecastMock,
    )
    def test_setup_with_config(self):
        """Test the platform setup with configuration."""
        setup_component(self.hass, "sensor", VALID_CONFIG_MINIMAL)
        self.hass.block_till_done()

        state = self.hass.states.get("sensor.dark_sky_summary")
        assert state is not None

    def test_setup_with_invalid_config(self):
        """Test the platform setup with invalid configuration."""
        setup_component(self.hass, "sensor", INVALID_CONFIG_MINIMAL)
        self.hass.block_till_done()

        state = self.hass.states.get("sensor.dark_sky_summary")
        assert state is None

    @patch(
        "homeassistant.components.darksky.sensor.forecastio.load_forecast",
        new=load_forecastMock,
    )
    def test_setup_with_language_config(self):
        """Test the platform setup with language configuration."""
        setup_component(self.hass, "sensor", VALID_CONFIG_LANG_DE)
        self.hass.block_till_done()

        state = self.hass.states.get("sensor.dark_sky_summary")
        assert state is not None

    def test_setup_with_invalid_language_config(self):
        """Test the platform setup with language configuration."""
        setup_component(self.hass, "sensor", INVALID_CONFIG_LANG)
        self.hass.block_till_done()

        state = self.hass.states.get("sensor.dark_sky_summary")
        assert state is None

    @patch("forecastio.api.get_forecast")
    def test_setup_bad_api_key(self, mock_get_forecast):
        """Test for handling a bad API key."""
        # The Dark Sky API wrapper that we use raises an HTTP error
        # when you try to use a bad (or no) API key.
        url = "https://api.darksky.net/forecast/{}/{},{}?units=auto".format(
            self.key, str(self.lat), str(self.lon)
        )
        msg = f"400 Client Error: Bad Request for url: {url}"
        mock_get_forecast.side_effect = HTTPError(msg)

        response = darksky.setup_platform(
            self.hass, VALID_CONFIG_MINIMAL["sensor"], MagicMock()
        )
        assert not response

    @patch(
        "homeassistant.components.darksky.sensor.forecastio.load_forecast",
        new=load_forecastMock,
    )
    def test_setup_with_alerts_config(self):
        """Test the platform setup with alert configuration."""
        setup_component(self.hass, "sensor", VALID_CONFIG_ALERTS)
        self.hass.block_till_done()

        state = self.hass.states.get("sensor.dark_sky_alerts")
        assert state.state == "0"

    @requests_mock.Mocker()
    @patch("forecastio.api.get_forecast", wraps=forecastio.api.get_forecast)
    def test_setup(self, mock_req, mock_get_forecast):
        """Test for successfully setting up the forecast.io platform."""
        uri = (
            r"https://api.(darksky.net|forecast.io)\/forecast\/(\w+)\/"
            r"(-?\d+\.?\d*),(-?\d+\.?\d*)"
        )
        mock_req.get(re.compile(uri), text=load_fixture("darksky.json"))

        assert setup_component(self.hass, "sensor", VALID_CONFIG_MINIMAL)
        self.hass.block_till_done()

        assert mock_get_forecast.called
        assert mock_get_forecast.call_count == 1
        assert len(self.hass.states.entity_ids()) == 13

        state = self.hass.states.get("sensor.dark_sky_summary")
        assert state is not None
        assert state.state == "Clear"
        assert state.attributes.get("friendly_name") == "Dark Sky Summary"
        state = self.hass.states.get("sensor.dark_sky_alerts")
        assert state.state == "2"

        state = self.hass.states.get("sensor.dark_sky_daytime_high_temperature_1d")
        assert state is not None
        assert state.attributes.get("device_class") == "temperature"
