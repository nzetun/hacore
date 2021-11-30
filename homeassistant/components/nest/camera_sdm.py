"""Support for Google Nest SDM Cameras."""
from __future__ import annotations

from collections.abc import Callable
import datetime
import logging
from pathlib import Path
from typing import Any

from google_nest_sdm.camera_traits import (
    CameraEventImageTrait,
    CameraImageTrait,
    CameraLiveStreamTrait,
    EventImageGenerator,
    RtspStream,
    StreamingProtocol,
)
from google_nest_sdm.device import Device
from google_nest_sdm.event import ImageEventBase
from google_nest_sdm.exceptions import GoogleNestException
from haffmpeg.tools import IMAGE_JPEG

from homeassistant.components.camera import SUPPORT_STREAM, Camera
from homeassistant.components.camera.const import STREAM_TYPE_HLS, STREAM_TYPE_WEB_RTC
from homeassistant.components.ffmpeg import async_get_image
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, PlatformNotReady
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import utcnow

from .const import DATA_SUBSCRIBER, DOMAIN
from .device_info import NestDeviceInfo

_LOGGER = logging.getLogger(__name__)

PLACEHOLDER = Path(__file__).parent / "placeholder.png"

# Used to schedule an alarm to refresh the stream before expiration
STREAM_EXPIRATION_BUFFER = datetime.timedelta(seconds=30)


async def async_setup_sdm_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the cameras."""

    subscriber = hass.data[DOMAIN][DATA_SUBSCRIBER]
    try:
        device_manager = await subscriber.async_get_device_manager()
    except GoogleNestException as err:
        raise PlatformNotReady from err

    # Fetch initial data so we have data when entities subscribe.

    entities = []
    for device in device_manager.devices.values():
        if (
            CameraImageTrait.NAME in device.traits
            or CameraLiveStreamTrait.NAME in device.traits
        ):
            entities.append(NestCamera(device))
    async_add_entities(entities)


class NestCamera(Camera):
    """Devices that support cameras."""

    def __init__(self, device: Device) -> None:
        """Initialize the camera."""
        super().__init__()
        self._device = device
        self._device_info = NestDeviceInfo(device)
        self._stream: RtspStream | None = None
        self._stream_refresh_unsub: Callable[[], None] | None = None
        # Cache of most recent event image
        self._event_id: str | None = None
        self._event_image_bytes: bytes | None = None
        self._event_image_cleanup_unsub: Callable[[], None] | None = None
        self._attr_is_streaming = CameraLiveStreamTrait.NAME in self._device.traits
        self._placeholder_image: bytes | None = None

    @property
    def should_poll(self) -> bool:
        """Disable polling since entities have state pushed via pubsub."""
        return False

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        # The API "name" field is a unique device identifier.
        return f"{self._device.name}-camera"

    @property
    def name(self) -> str | None:
        """Return the name of the camera."""
        return self._device_info.device_name

    @property
    def device_info(self) -> DeviceInfo:
        """Return device specific attributes."""
        return self._device_info.device_info

    @property
    def brand(self) -> str | None:
        """Return the camera brand."""
        return self._device_info.device_brand

    @property
    def model(self) -> str | None:
        """Return the camera model."""
        return self._device_info.device_model

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        supported_features = 0
        if CameraLiveStreamTrait.NAME in self._device.traits:
            supported_features |= SUPPORT_STREAM
        return supported_features

    @property
    def frontend_stream_type(self) -> str | None:
        """Return the type of stream supported by this camera."""
        if CameraLiveStreamTrait.NAME not in self._device.traits:
            return None
        trait = self._device.traits[CameraLiveStreamTrait.NAME]
        if StreamingProtocol.WEB_RTC in trait.supported_protocols:
            return STREAM_TYPE_WEB_RTC
        return STREAM_TYPE_HLS

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        if not self.supported_features & SUPPORT_STREAM:
            return None
        if CameraLiveStreamTrait.NAME not in self._device.traits:
            return None
        trait = self._device.traits[CameraLiveStreamTrait.NAME]
        if StreamingProtocol.RTSP not in trait.supported_protocols:
            return None
        if not self._stream:
            _LOGGER.debug("Fetching stream url")
            try:
                self._stream = await trait.generate_rtsp_stream()
            except GoogleNestException as err:
                raise HomeAssistantError(f"Nest API error: {err}") from err
            self._schedule_stream_refresh()
        assert self._stream
        if self._stream.expires_at < utcnow():
            _LOGGER.warning("Stream already expired")
        return self._stream.rtsp_stream_url

    def _schedule_stream_refresh(self) -> None:
        """Schedules an alarm to refresh the stream url before expiration."""
        assert self._stream
        _LOGGER.debug("New stream url expires at %s", self._stream.expires_at)
        refresh_time = self._stream.expires_at - STREAM_EXPIRATION_BUFFER
        # Schedule an alarm to extend the stream
        if self._stream_refresh_unsub is not None:
            self._stream_refresh_unsub()

        self._stream_refresh_unsub = async_track_point_in_utc_time(
            self.hass,
            self._handle_stream_refresh,
            refresh_time,
        )

    async def _handle_stream_refresh(self, now: datetime.datetime) -> None:
        """Alarm that fires to check if the stream should be refreshed."""
        if not self._stream:
            return
        _LOGGER.debug("Extending stream url")
        try:
            self._stream = await self._stream.extend_rtsp_stream()
        except GoogleNestException as err:
            _LOGGER.debug("Failed to extend stream: %s", err)
            # Next attempt to catch a url will get a new one
            self._stream = None
            if self.stream:
                self.stream.stop()
                self.stream = None
            return
        # Update the stream worker with the latest valid url
        if self.stream:
            self.stream.update_source(self._stream.rtsp_stream_url)
        self._schedule_stream_refresh()

    async def async_will_remove_from_hass(self) -> None:
        """Invalidates the RTSP token when unloaded."""
        if self._stream:
            _LOGGER.debug("Invalidating stream")
            await self._stream.stop_rtsp_stream()
        if self._stream_refresh_unsub:
            self._stream_refresh_unsub()
        self._event_id = None
        self._event_image_bytes = None
        if self._event_image_cleanup_unsub is not None:
            self._event_image_cleanup_unsub()

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to register update signal handler."""
        self.async_on_remove(
            self._device.add_update_listener(self.async_write_ha_state)
        )

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        # Returns the snapshot of the last event for ~30 seconds after the event
        active_event_image = await self._async_active_event_image()
        if active_event_image:
            return active_event_image
        # Fetch still image from the live stream
        stream_url = await self.stream_source()
        if not stream_url:
            if self.frontend_stream_type != STREAM_TYPE_WEB_RTC:
                return None
            # Nest Web RTC cams only have image previews for events, and not
            # for "now" by design to save batter, and need a placeholder.
            if not self._placeholder_image:
                self._placeholder_image = await self.hass.async_add_executor_job(
                    PLACEHOLDER.read_bytes
                )
            return self._placeholder_image
        return await async_get_image(self.hass, stream_url, output_format=IMAGE_JPEG)

    async def _async_active_event_image(self) -> bytes | None:
        """Return image from any active events happening."""
        if CameraEventImageTrait.NAME not in self._device.traits:
            return None
        if not (trait := self._device.active_event_trait):
            return None
        # Reuse image bytes if they have already been fetched
        if not isinstance(trait, EventImageGenerator):
            return None
        event: ImageEventBase | None = trait.last_event
        if not event:
            return None
        if self._event_id is not None and self._event_id == event.event_id:
            return self._event_image_bytes
        _LOGGER.debug("Generating event image URL for event_id %s", event.event_id)
        image_bytes = await self._async_fetch_active_event_image(trait)
        if image_bytes is None:
            return None
        self._event_id = event.event_id
        self._event_image_bytes = image_bytes
        self._schedule_event_image_cleanup(event.expires_at)
        return image_bytes

    async def _async_fetch_active_event_image(
        self, trait: EventImageGenerator
    ) -> bytes | None:
        """Return image bytes for an active event."""
        # pylint: disable=no-self-use
        try:
            event_image = await trait.generate_active_event_image()
        except GoogleNestException as err:
            _LOGGER.debug("Unable to generate event image URL: %s", err)
            return None
        if not event_image:
            return None
        try:
            return await event_image.contents()
        except GoogleNestException as err:
            _LOGGER.debug("Unable to fetch event image: %s", err)
            return None

    def _schedule_event_image_cleanup(self, point_in_time: datetime.datetime) -> None:
        """Schedules an alarm to remove the image bytes from memory, honoring expiration."""
        if self._event_image_cleanup_unsub is not None:
            self._event_image_cleanup_unsub()
        self._event_image_cleanup_unsub = async_track_point_in_utc_time(
            self.hass,
            self._handle_event_image_cleanup,
            point_in_time,
        )

    def _handle_event_image_cleanup(self, now: Any) -> None:
        """Clear images cached from events and scheduled callback."""
        self._event_id = None
        self._event_image_bytes = None
        self._event_image_cleanup_unsub = None

    async def async_handle_web_rtc_offer(self, offer_sdp: str) -> str:
        """Return the source of the stream."""
        trait: CameraLiveStreamTrait = self._device.traits[CameraLiveStreamTrait.NAME]
        try:
            stream = await trait.generate_web_rtc_stream(offer_sdp)
        except GoogleNestException as err:
            raise HomeAssistantError(f"Nest API error: {err}") from err
        return stream.answer_sdp
