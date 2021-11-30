"""Component to pressing a button as platforms."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import DOMAIN, SERVICE_PRESS

SCAN_INTERVAL = timedelta(seconds=30)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)

DEVICE_CLASS_RESTART = "restart"
DEVICE_CLASS_UPDATE = "update"

DEVICE_CLASSES = [DEVICE_CLASS_RESTART, DEVICE_CLASS_UPDATE]

DEVICE_CLASSES_SCHEMA = vol.All(vol.Lower, vol.In(DEVICE_CLASSES))


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Button entities."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_PRESS,
        {},
        "_async_press_action",
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


@dataclass
class ButtonEntityDescription(EntityDescription):
    """A class that describes button entities."""


class ButtonEntity(RestoreEntity):
    """Representation of a Button entity."""

    entity_description: ButtonEntityDescription
    _attr_should_poll = False
    _attr_device_class: None = None
    _attr_state: None = None
    __last_pressed: datetime | None = None

    @property
    @final
    def state(self) -> str | None:
        """Return the entity state."""
        if self.__last_pressed is None:
            return None
        return self.__last_pressed.isoformat()

    @final
    async def _async_press_action(self) -> None:
        """Press the button (from e.g., service call).

        Should not be overridden, handle setting last press timestamp.
        """
        self.__last_pressed = dt_util.utcnow()
        self.async_write_ha_state()
        await self.async_press()

    async def async_added_to_hass(self) -> None:
        """Call when the button is added to hass."""
        state = await self.async_get_last_state()
        if state is not None and state.state is not None:
            self.__last_pressed = dt_util.parse_datetime(state.state)

    def press(self) -> None:
        """Press the button."""
        raise NotImplementedError()

    async def async_press(self) -> None:
        """Press the button."""
        await self.hass.async_add_executor_job(self.press)
