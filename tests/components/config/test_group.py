"""Test Group config panel."""
from http import HTTPStatus
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from homeassistant.bootstrap import async_setup_component
from homeassistant.components import config
from homeassistant.components.config import group
from homeassistant.util.file import write_utf8_file
from homeassistant.util.yaml import dump, load_yaml

VIEW_NAME = "api:config:group:config"


async def test_get_device_config(hass, hass_client):
    """Test getting device config."""
    with patch.object(config, "SECTIONS", ["group"]):
        await async_setup_component(hass, "config", {})

    client = await hass_client()

    def mock_read(path):
        """Mock reading data."""
        return {"hello.beer": {"free": "beer"}, "other.entity": {"do": "something"}}

    with patch("homeassistant.components.config._read", mock_read):
        resp = await client.get("/api/config/group/config/hello.beer")

    assert resp.status == HTTPStatus.OK
    result = await resp.json()

    assert result == {"free": "beer"}


async def test_update_device_config(hass, hass_client):
    """Test updating device config."""
    with patch.object(config, "SECTIONS", ["group"]):
        await async_setup_component(hass, "config", {})

    client = await hass_client()

    orig_data = {
        "hello.beer": {"ignored": True},
        "other.entity": {"polling_intensity": 2},
    }

    def mock_read(path):
        """Mock reading data."""
        return orig_data

    written = []

    def mock_write(path, data):
        """Mock writing data."""
        written.append(data)

    mock_call = AsyncMock()

    with patch("homeassistant.components.config._read", mock_read), patch(
        "homeassistant.components.config._write", mock_write
    ), patch.object(hass.services, "async_call", mock_call):
        resp = await client.post(
            "/api/config/group/config/hello_beer",
            data=json.dumps(
                {"name": "Beer", "entities": ["light.top", "light.bottom"]}
            ),
        )
        await hass.async_block_till_done()

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"result": "ok"}

    orig_data["hello_beer"]["name"] = "Beer"
    orig_data["hello_beer"]["entities"] = ["light.top", "light.bottom"]

    assert written[0] == orig_data
    mock_call.assert_called_once_with("group", "reload")


async def test_update_device_config_invalid_key(hass, hass_client):
    """Test updating device config."""
    with patch.object(config, "SECTIONS", ["group"]):
        await async_setup_component(hass, "config", {})

    client = await hass_client()

    resp = await client.post(
        "/api/config/group/config/not a slug", data=json.dumps({"name": "YO"})
    )

    assert resp.status == HTTPStatus.BAD_REQUEST


async def test_update_device_config_invalid_data(hass, hass_client):
    """Test updating device config."""
    with patch.object(config, "SECTIONS", ["group"]):
        await async_setup_component(hass, "config", {})

    client = await hass_client()

    resp = await client.post(
        "/api/config/group/config/hello_beer", data=json.dumps({"invalid_option": 2})
    )

    assert resp.status == HTTPStatus.BAD_REQUEST


async def test_update_device_config_invalid_json(hass, hass_client):
    """Test updating device config."""
    with patch.object(config, "SECTIONS", ["group"]):
        await async_setup_component(hass, "config", {})

    client = await hass_client()

    resp = await client.post("/api/config/group/config/hello_beer", data="not json")

    assert resp.status == HTTPStatus.BAD_REQUEST


async def test_update_config_write_to_temp_file(hass, hass_client, tmpdir):
    """Test config with a temp file."""
    test_dir = await hass.async_add_executor_job(tmpdir.mkdir, "files")
    group_yaml = Path(test_dir / "group.yaml")

    with patch.object(group, "GROUP_CONFIG_PATH", group_yaml), patch.object(
        config, "SECTIONS", ["group"]
    ):
        await async_setup_component(hass, "config", {})

    client = await hass_client()

    orig_data = {
        "hello.beer": {"ignored": True},
        "other.entity": {"polling_intensity": 2},
    }
    contents = dump(orig_data)
    await hass.async_add_executor_job(write_utf8_file, group_yaml, contents)

    mock_call = AsyncMock()

    with patch.object(hass.services, "async_call", mock_call):
        resp = await client.post(
            "/api/config/group/config/hello_beer",
            data=json.dumps(
                {"name": "Beer", "entities": ["light.top", "light.bottom"]}
            ),
        )
        await hass.async_block_till_done()

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"result": "ok"}

    new_data = await hass.async_add_executor_job(load_yaml, group_yaml)

    assert new_data == {
        **orig_data,
        "hello_beer": {
            "name": "Beer",
            "entities": ["light.top", "light.bottom"],
        },
    }
    mock_call.assert_called_once_with("group", "reload")
