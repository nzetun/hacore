"""Entity representing a Sonos number control."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.const import ENTITY_CATEGORY_CONFIG
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import SONOS_CREATE_LEVELS
from .entity import SonosEntity
from .helpers import soco_error
from .speaker import SonosSpeaker

LEVEL_TYPES = ("bass", "treble")


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Sonos number platform from a config entry."""

    async def _async_create_entities(speaker: SonosSpeaker) -> None:
        entities = []
        for level_type in LEVEL_TYPES:
            entities.append(SonosLevelEntity(speaker, level_type))
        async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SONOS_CREATE_LEVELS, _async_create_entities)
    )


class SonosLevelEntity(SonosEntity, NumberEntity):
    """Representation of a Sonos level entity."""

    _attr_entity_category = ENTITY_CATEGORY_CONFIG
    _attr_min_value = -10
    _attr_max_value = 10

    def __init__(self, speaker: SonosSpeaker, level_type: str) -> None:
        """Initialize the level entity."""
        super().__init__(speaker)
        self.level_type = level_type

    @property
    def unique_id(self) -> str:
        """Return the unique ID."""
        return f"{self.soco.uid}-{self.level_type}"

    @property
    def name(self) -> str:
        """Return the name."""
        return f"{self.speaker.zone_name} {self.level_type.capitalize()}"

    async def _async_poll(self) -> None:
        """Poll the value if subscriptions are not working."""
        # Handled by SonosSpeaker

    @soco_error()
    def set_value(self, value: float) -> None:
        """Set a new value."""
        setattr(self.soco, self.level_type, value)

    @property
    def value(self) -> float:
        """Return the current value."""
        return getattr(self.speaker, self.level_type)
