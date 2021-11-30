"""Test Automation config panel."""
from http import HTTPStatus
import json
from unittest.mock import patch

import pytest

from homeassistant.bootstrap import async_setup_component
from homeassistant.components import config
from homeassistant.helpers import entity_registry as er
from homeassistant.util.yaml import dump


@pytest.fixture
async def setup_scene(hass, scene_config):
    """Set up scene integration."""
    assert await async_setup_component(hass, "scene", {"scene": scene_config})


@pytest.mark.parametrize("scene_config", ({},))
async def test_create_scene(hass, hass_client, setup_scene):
    """Test creating a scene."""
    with patch.object(config, "SECTIONS", ["scene"]):
        await async_setup_component(hass, "config", {})

    client = await hass_client()

    def mock_read(path):
        """Mock reading data."""
        return None

    written = []

    def mock_write(path, data):
        """Mock writing data."""
        data = dump(data)
        written.append(data)

    with patch("homeassistant.components.config._read", mock_read), patch(
        "homeassistant.components.config._write", mock_write
    ), patch("homeassistant.config.async_hass_config_yaml", return_value={}):
        resp = await client.post(
            "/api/config/scene/config/light_off",
            data=json.dumps(
                {
                    # "id": "light_off",
                    "name": "Lights off",
                    "entities": {"light.bedroom": {"state": "off"}},
                }
            ),
        )

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"result": "ok"}

    assert len(written) == 1
    written_yaml = written[0]
    assert (
        written_yaml
        == """- id: light_off
  name: Lights off
  entities:
    light.bedroom:
      state: 'off'
"""
    )


@pytest.mark.parametrize("scene_config", ({},))
async def test_update_scene(hass, hass_client, setup_scene):
    """Test updating a scene."""
    with patch.object(config, "SECTIONS", ["scene"]):
        await async_setup_component(hass, "config", {})

    client = await hass_client()

    orig_data = [{"id": "light_on"}, {"id": "light_off"}]

    def mock_read(path):
        """Mock reading data."""
        return orig_data

    written = []

    def mock_write(path, data):
        """Mock writing data."""
        data = dump(data)
        written.append(data)

    with patch("homeassistant.components.config._read", mock_read), patch(
        "homeassistant.components.config._write", mock_write
    ), patch("homeassistant.config.async_hass_config_yaml", return_value={}):
        resp = await client.post(
            "/api/config/scene/config/light_off",
            data=json.dumps(
                {
                    "id": "light_off",
                    "name": "Lights off",
                    "entities": {"light.bedroom": {"state": "off"}},
                }
            ),
        )

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"result": "ok"}

    assert len(written) == 1
    written_yaml = written[0]
    assert (
        written_yaml
        == """- id: light_on
- id: light_off
  name: Lights off
  entities:
    light.bedroom:
      state: 'off'
"""
    )


@pytest.mark.parametrize("scene_config", ({},))
async def test_bad_formatted_scene(hass, hass_client, setup_scene):
    """Test that we handle scene without ID."""
    with patch.object(config, "SECTIONS", ["scene"]):
        await async_setup_component(hass, "config", {})

    client = await hass_client()

    orig_data = [
        {
            # No ID
            "entities": {"light.bedroom": "on"}
        },
        {"id": "light_off"},
    ]

    def mock_read(path):
        """Mock reading data."""
        return orig_data

    written = []

    def mock_write(path, data):
        """Mock writing data."""
        written.append(data)

    with patch("homeassistant.components.config._read", mock_read), patch(
        "homeassistant.components.config._write", mock_write
    ), patch("homeassistant.config.async_hass_config_yaml", return_value={}):
        resp = await client.post(
            "/api/config/scene/config/light_off",
            data=json.dumps(
                {
                    "id": "light_off",
                    "name": "Lights off",
                    "entities": {"light.bedroom": {"state": "off"}},
                }
            ),
        )

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"result": "ok"}

    # Verify ID added to orig_data
    assert "id" in orig_data[0]

    assert orig_data[1] == {
        "id": "light_off",
        "name": "Lights off",
        "entities": {"light.bedroom": {"state": "off"}},
    }


@pytest.mark.parametrize(
    "scene_config",
    (
        [
            {"id": "light_on", "name": "Light on", "entities": {}},
            {"id": "light_off", "name": "Light off", "entities": {}},
        ],
    ),
)
async def test_delete_scene(hass, hass_client, setup_scene):
    """Test deleting a scene."""
    ent_reg = er.async_get(hass)

    assert len(ent_reg.entities) == 2

    with patch.object(config, "SECTIONS", ["scene"]):
        assert await async_setup_component(hass, "config", {})

    client = await hass_client()

    orig_data = [{"id": "light_on"}, {"id": "light_off"}]

    def mock_read(path):
        """Mock reading data."""
        return orig_data

    written = []

    def mock_write(path, data):
        """Mock writing data."""
        written.append(data)

    with patch("homeassistant.components.config._read", mock_read), patch(
        "homeassistant.components.config._write", mock_write
    ), patch("homeassistant.config.async_hass_config_yaml", return_value={}):
        resp = await client.delete("/api/config/scene/config/light_on")
        await hass.async_block_till_done()

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"result": "ok"}

    assert len(written) == 1
    assert written[0][0]["id"] == "light_off"

    assert len(ent_reg.entities) == 1
