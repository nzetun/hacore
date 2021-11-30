"""The tests for the camera component."""
import asyncio
import base64
from http import HTTPStatus
import io
from unittest.mock import Mock, PropertyMock, mock_open, patch

import pytest

from homeassistant.components import camera
from homeassistant.components.camera.const import (
    DOMAIN,
    PREF_PRELOAD_STREAM,
    STREAM_TYPE_WEB_RTC,
)
from homeassistant.components.camera.prefs import CameraEntityPreferences
from homeassistant.components.websocket_api.const import TYPE_RESULT
from homeassistant.config import async_process_ha_core_config
from homeassistant.const import ATTR_ENTITY_ID, EVENT_HOMEASSISTANT_START
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from .common import EMPTY_8_6_JPEG, mock_turbo_jpeg

from tests.components.camera import common


@pytest.fixture(name="mock_camera")
async def mock_camera_fixture(hass):
    """Initialize a demo camera platform."""
    assert await async_setup_component(
        hass, "camera", {camera.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.demo.camera.Path.read_bytes",
        return_value=b"Test",
    ):
        yield


@pytest.fixture(name="mock_camera_web_rtc")
async def mock_camera_web_rtc_fixture(hass):
    """Initialize a demo camera platform."""
    assert await async_setup_component(
        hass, "camera", {camera.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.camera.Camera.frontend_stream_type",
        new_callable=PropertyMock(return_value=STREAM_TYPE_WEB_RTC),
    ), patch(
        "homeassistant.components.camera.Camera.async_handle_web_rtc_offer",
        return_value="a=sendonly",
    ):
        yield


@pytest.fixture(name="mock_stream")
def mock_stream_fixture(hass):
    """Initialize a demo camera platform with streaming."""
    assert hass.loop.run_until_complete(
        async_setup_component(hass, "stream", {"stream": {}})
    )


@pytest.fixture(name="setup_camera_prefs")
def setup_camera_prefs_fixture(hass):
    """Initialize HTTP API."""
    return common.mock_camera_prefs(hass, "camera.demo_camera")


@pytest.fixture(name="image_mock_url")
async def image_mock_url_fixture(hass):
    """Fixture for get_image tests."""
    await async_setup_component(
        hass, camera.DOMAIN, {camera.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()


async def test_get_image_from_camera(hass, image_mock_url):
    """Grab an image from camera entity."""

    with patch(
        "homeassistant.components.demo.camera.Path.read_bytes",
        autospec=True,
        return_value=b"Test",
    ) as mock_camera:
        image = await camera.async_get_image(hass, "camera.demo_camera")

    assert mock_camera.called
    assert image.content == b"Test"


async def test_legacy_async_get_image_signature_warns_only_once(
    hass, image_mock_url, caplog
):
    """Test that we only warn once when we encounter a legacy async_get_image function signature."""

    async def _legacy_async_camera_image(self):
        return b"Image"

    with patch(
        "homeassistant.components.demo.camera.DemoCamera.async_camera_image",
        new=_legacy_async_camera_image,
    ):
        image = await camera.async_get_image(hass, "camera.demo_camera")
        assert image.content == b"Image"
        assert "does not support requesting width and height" in caplog.text
        caplog.clear()

        image = await camera.async_get_image(hass, "camera.demo_camera")
        assert image.content == b"Image"
        assert "does not support requesting width and height" not in caplog.text


async def test_get_image_from_camera_with_width_height(hass, image_mock_url):
    """Grab an image from camera entity with width and height."""

    turbo_jpeg = mock_turbo_jpeg(
        first_width=16, first_height=12, second_width=300, second_height=200
    )
    with patch(
        "homeassistant.components.camera.img_util.TurboJPEGSingleton.instance",
        return_value=turbo_jpeg,
    ), patch(
        "homeassistant.components.demo.camera.Path.read_bytes",
        autospec=True,
        return_value=b"Test",
    ) as mock_camera:
        image = await camera.async_get_image(
            hass, "camera.demo_camera", width=640, height=480
        )

    assert mock_camera.called
    assert image.content == b"Test"


async def test_get_image_from_camera_with_width_height_scaled(hass, image_mock_url):
    """Grab an image from camera entity with width and height and scale it."""

    turbo_jpeg = mock_turbo_jpeg(
        first_width=16, first_height=12, second_width=300, second_height=200
    )
    with patch(
        "homeassistant.components.camera.img_util.TurboJPEGSingleton.instance",
        return_value=turbo_jpeg,
    ), patch(
        "homeassistant.components.demo.camera.Path.read_bytes",
        autospec=True,
        return_value=b"Valid jpeg",
    ) as mock_camera:
        image = await camera.async_get_image(
            hass, "camera.demo_camera", width=4, height=3
        )

    assert mock_camera.called
    assert image.content_type == "image/jpg"
    assert image.content == EMPTY_8_6_JPEG


async def test_get_image_from_camera_not_jpeg(hass, image_mock_url):
    """Grab an image from camera entity that we cannot scale."""

    turbo_jpeg = mock_turbo_jpeg(
        first_width=16, first_height=12, second_width=300, second_height=200
    )
    with patch(
        "homeassistant.components.camera.img_util.TurboJPEGSingleton.instance",
        return_value=turbo_jpeg,
    ), patch(
        "homeassistant.components.demo.camera.Path.read_bytes",
        autospec=True,
        return_value=b"png",
    ) as mock_camera:
        image = await camera.async_get_image(
            hass, "camera.demo_camera_png", width=4, height=3
        )

    assert mock_camera.called
    assert image.content_type == "image/png"
    assert image.content == b"png"


async def test_get_stream_source_from_camera(hass, mock_camera):
    """Fetch stream source from camera entity."""

    with patch(
        "homeassistant.components.camera.Camera.stream_source",
        return_value="rtsp://127.0.0.1/stream",
    ) as mock_camera_stream_source:
        stream_source = await camera.async_get_stream_source(hass, "camera.demo_camera")

    assert mock_camera_stream_source.called
    assert stream_source == "rtsp://127.0.0.1/stream"


async def test_get_image_without_exists_camera(hass, image_mock_url):
    """Try to get image without exists camera."""
    with patch(
        "homeassistant.helpers.entity_component.EntityComponent.get_entity",
        return_value=None,
    ), pytest.raises(HomeAssistantError):
        await camera.async_get_image(hass, "camera.demo_camera")


async def test_get_image_with_timeout(hass, image_mock_url):
    """Try to get image with timeout."""
    with patch(
        "homeassistant.components.demo.camera.DemoCamera.async_camera_image",
        side_effect=asyncio.TimeoutError,
    ), pytest.raises(HomeAssistantError):
        await camera.async_get_image(hass, "camera.demo_camera")


async def test_get_image_fails(hass, image_mock_url):
    """Try to get image with timeout."""
    with patch(
        "homeassistant.components.demo.camera.DemoCamera.async_camera_image",
        return_value=None,
    ), pytest.raises(HomeAssistantError):
        await camera.async_get_image(hass, "camera.demo_camera")


async def test_snapshot_service(hass, mock_camera):
    """Test snapshot service."""
    mopen = mock_open()

    with patch("homeassistant.components.camera.open", mopen, create=True), patch(
        "homeassistant.components.camera.os.path.exists",
        Mock(spec="os.path.exists", return_value=True),
    ), patch.object(hass.config, "is_allowed_path", return_value=True):
        await hass.services.async_call(
            camera.DOMAIN,
            camera.SERVICE_SNAPSHOT,
            {
                ATTR_ENTITY_ID: "camera.demo_camera",
                camera.ATTR_FILENAME: "/test/snapshot.jpg",
            },
            blocking=True,
        )

        mock_write = mopen().write

        assert len(mock_write.mock_calls) == 1
        assert mock_write.mock_calls[0][1][0] == b"Test"


async def test_websocket_camera_thumbnail(hass, hass_ws_client, mock_camera):
    """Test camera_thumbnail websocket command."""
    await async_setup_component(hass, "camera", {})

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 5, "type": "camera_thumbnail", "entity_id": "camera.demo_camera"}
    )

    msg = await client.receive_json()

    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"]["content_type"] == "image/jpg"
    assert msg["result"]["content"] == base64.b64encode(b"Test").decode("utf-8")


async def test_websocket_stream_no_source(
    hass, hass_ws_client, mock_camera, mock_stream
):
    """Test camera/stream websocket command with camera with no source."""
    await async_setup_component(hass, "camera", {})

    # Request playlist through WebSocket
    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 6, "type": "camera/stream", "entity_id": "camera.demo_camera"}
    )
    msg = await client.receive_json()

    # Assert WebSocket response
    assert msg["id"] == 6
    assert msg["type"] == TYPE_RESULT
    assert not msg["success"]


async def test_websocket_camera_stream(hass, hass_ws_client, mock_camera, mock_stream):
    """Test camera/stream websocket command."""
    await async_setup_component(hass, "camera", {})

    with patch(
        "homeassistant.components.camera.Stream.endpoint_url",
        return_value="http://home.assistant/playlist.m3u8",
    ) as mock_stream_view_url, patch(
        "homeassistant.components.demo.camera.DemoCamera.stream_source",
        return_value="http://example.com",
    ):
        # Request playlist through WebSocket
        client = await hass_ws_client(hass)
        await client.send_json(
            {"id": 6, "type": "camera/stream", "entity_id": "camera.demo_camera"}
        )
        msg = await client.receive_json()

        # Assert WebSocket response
        assert mock_stream_view_url.called
        assert msg["id"] == 6
        assert msg["type"] == TYPE_RESULT
        assert msg["success"]
        assert msg["result"]["url"][-13:] == "playlist.m3u8"


async def test_websocket_get_prefs(hass, hass_ws_client, mock_camera):
    """Test get camera preferences websocket command."""
    await async_setup_component(hass, "camera", {})

    # Request preferences through websocket
    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 7, "type": "camera/get_prefs", "entity_id": "camera.demo_camera"}
    )
    msg = await client.receive_json()

    # Assert WebSocket response
    assert msg["success"]


async def test_websocket_update_prefs(
    hass, hass_ws_client, mock_camera, setup_camera_prefs
):
    """Test updating preference."""
    await async_setup_component(hass, "camera", {})
    assert setup_camera_prefs[PREF_PRELOAD_STREAM]
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 8,
            "type": "camera/update_prefs",
            "entity_id": "camera.demo_camera",
            "preload_stream": False,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert not setup_camera_prefs[PREF_PRELOAD_STREAM]
    assert (
        response["result"][PREF_PRELOAD_STREAM]
        == setup_camera_prefs[PREF_PRELOAD_STREAM]
    )


async def test_play_stream_service_no_source(hass, mock_camera, mock_stream):
    """Test camera play_stream service."""
    data = {
        ATTR_ENTITY_ID: "camera.demo_camera",
        camera.ATTR_MEDIA_PLAYER: "media_player.test",
    }
    with pytest.raises(HomeAssistantError):
        # Call service
        await hass.services.async_call(
            camera.DOMAIN, camera.SERVICE_PLAY_STREAM, data, blocking=True
        )


async def test_handle_play_stream_service(hass, mock_camera, mock_stream):
    """Test camera play_stream service."""
    await async_process_ha_core_config(
        hass,
        {"external_url": "https://example.com"},
    )
    await async_setup_component(hass, "media_player", {})
    with patch(
        "homeassistant.components.camera.Stream.endpoint_url",
    ) as mock_request_stream, patch(
        "homeassistant.components.demo.camera.DemoCamera.stream_source",
        return_value="http://example.com",
    ):
        # Call service
        await hass.services.async_call(
            camera.DOMAIN,
            camera.SERVICE_PLAY_STREAM,
            {
                ATTR_ENTITY_ID: "camera.demo_camera",
                camera.ATTR_MEDIA_PLAYER: "media_player.test",
            },
            blocking=True,
        )
        # So long as we request the stream, the rest should be covered
        # by the play_media service tests.
        assert mock_request_stream.called


async def test_no_preload_stream(hass, mock_stream):
    """Test camera preload preference."""
    demo_prefs = CameraEntityPreferences({PREF_PRELOAD_STREAM: False})
    with patch(
        "homeassistant.components.camera.Stream.endpoint_url",
    ) as mock_request_stream, patch(
        "homeassistant.components.camera.prefs.CameraPreferences.get",
        return_value=demo_prefs,
    ), patch(
        "homeassistant.components.demo.camera.DemoCamera.stream_source",
        new_callable=PropertyMock,
    ) as mock_stream_source:
        mock_stream_source.return_value = io.BytesIO()
        await async_setup_component(hass, "camera", {DOMAIN: {"platform": "demo"}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()
        assert not mock_request_stream.called


async def test_preload_stream(hass, mock_stream):
    """Test camera preload preference."""
    demo_prefs = CameraEntityPreferences({PREF_PRELOAD_STREAM: True})
    with patch(
        "homeassistant.components.camera.create_stream"
    ) as mock_create_stream, patch(
        "homeassistant.components.camera.prefs.CameraPreferences.get",
        return_value=demo_prefs,
    ), patch(
        "homeassistant.components.demo.camera.DemoCamera.stream_source",
        return_value="http://example.com",
    ):
        assert await async_setup_component(
            hass, "camera", {DOMAIN: {"platform": "demo"}}
        )
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()
        assert mock_create_stream.called


async def test_record_service_invalid_path(hass, mock_camera):
    """Test record service with invalid path."""
    with patch.object(
        hass.config, "is_allowed_path", return_value=False
    ), pytest.raises(HomeAssistantError):
        # Call service
        await hass.services.async_call(
            camera.DOMAIN,
            camera.SERVICE_RECORD,
            {
                ATTR_ENTITY_ID: "camera.demo_camera",
                camera.CONF_FILENAME: "/my/invalid/path",
            },
            blocking=True,
        )


async def test_record_service(hass, mock_camera, mock_stream):
    """Test record service."""
    with patch(
        "homeassistant.components.demo.camera.DemoCamera.stream_source",
        return_value="http://example.com",
    ), patch(
        "homeassistant.components.stream.Stream.async_record",
        autospec=True,
    ) as mock_record:
        # Call service
        await hass.services.async_call(
            camera.DOMAIN,
            camera.SERVICE_RECORD,
            {ATTR_ENTITY_ID: "camera.demo_camera", camera.CONF_FILENAME: "/my/path"},
            blocking=True,
        )
        # So long as we call stream.record, the rest should be covered
        # by those tests.
        assert mock_record.called


async def test_camera_proxy_stream(hass, mock_camera, hass_client):
    """Test record service."""

    client = await hass_client()

    response = await client.get("/api/camera_proxy_stream/camera.demo_camera")
    assert response.status == HTTPStatus.OK

    with patch(
        "homeassistant.components.demo.camera.DemoCamera.handle_async_mjpeg_stream",
        return_value=None,
    ):
        response = await client.get("/api/camera_proxy_stream/camera.demo_camera")
        assert response.status == HTTPStatus.BAD_GATEWAY


async def test_websocket_web_rtc_offer(
    hass,
    hass_ws_client,
    mock_camera_web_rtc,
):
    """Test initiating a WebRTC stream with offer and answer."""
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 9,
            "type": "camera/web_rtc_offer",
            "entity_id": "camera.demo_camera",
            "offer": "v=0\r\n",
        }
    )
    response = await client.receive_json()

    assert response["id"] == 9
    assert response["type"] == TYPE_RESULT
    assert response["success"]
    assert response["result"]["answer"] == "a=sendonly"


async def test_websocket_web_rtc_offer_invalid_entity(
    hass,
    hass_ws_client,
    mock_camera_web_rtc,
):
    """Test WebRTC with a camera entity that does not exist."""
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 9,
            "type": "camera/web_rtc_offer",
            "entity_id": "camera.does_not_exist",
            "offer": "v=0\r\n",
        }
    )
    response = await client.receive_json()

    assert response["id"] == 9
    assert response["type"] == TYPE_RESULT
    assert not response["success"]


async def test_websocket_web_rtc_offer_missing_offer(
    hass,
    hass_ws_client,
    mock_camera_web_rtc,
):
    """Test WebRTC stream with missing required fields."""
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 9,
            "type": "camera/web_rtc_offer",
            "entity_id": "camera.demo_camera",
        }
    )
    response = await client.receive_json()

    assert response["id"] == 9
    assert response["type"] == TYPE_RESULT
    assert not response["success"]
    assert response["error"]["code"] == "invalid_format"


async def test_websocket_web_rtc_offer_failure(
    hass,
    hass_ws_client,
    mock_camera_web_rtc,
):
    """Test WebRTC stream that fails handling the offer."""
    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.camera.Camera.async_handle_web_rtc_offer",
        side_effect=HomeAssistantError("offer failed"),
    ):
        await client.send_json(
            {
                "id": 9,
                "type": "camera/web_rtc_offer",
                "entity_id": "camera.demo_camera",
                "offer": "v=0\r\n",
            }
        )
        response = await client.receive_json()

    assert response["id"] == 9
    assert response["type"] == TYPE_RESULT
    assert not response["success"]
    assert response["error"]["code"] == "web_rtc_offer_failed"
    assert response["error"]["message"] == "offer failed"


async def test_websocket_web_rtc_offer_timeout(
    hass,
    hass_ws_client,
    mock_camera_web_rtc,
):
    """Test WebRTC stream with timeout handling the offer."""
    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.camera.Camera.async_handle_web_rtc_offer",
        side_effect=asyncio.TimeoutError(),
    ):
        await client.send_json(
            {
                "id": 9,
                "type": "camera/web_rtc_offer",
                "entity_id": "camera.demo_camera",
                "offer": "v=0\r\n",
            }
        )
        response = await client.receive_json()

    assert response["id"] == 9
    assert response["type"] == TYPE_RESULT
    assert not response["success"]
    assert response["error"]["code"] == "web_rtc_offer_failed"
    assert response["error"]["message"] == "Timeout handling WebRTC offer"


async def test_websocket_web_rtc_offer_invalid_stream_type(
    hass,
    hass_ws_client,
    mock_camera,
):
    """Test WebRTC initiating for a camera with a different stream_type."""
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 9,
            "type": "camera/web_rtc_offer",
            "entity_id": "camera.demo_camera",
            "offer": "v=0\r\n",
        }
    )
    response = await client.receive_json()

    assert response["id"] == 9
    assert response["type"] == TYPE_RESULT
    assert not response["success"]
    assert response["error"]["code"] == "web_rtc_offer_failed"
