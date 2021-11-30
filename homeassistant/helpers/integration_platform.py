"""Helpers to help with integration platforms."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import logging
from typing import Any

from homeassistant.core import Event, HomeAssistant
from homeassistant.loader import async_get_integration, bind_hass
from homeassistant.setup import ATTR_COMPONENT, EVENT_COMPONENT_LOADED

_LOGGER = logging.getLogger(__name__)


@bind_hass
async def async_process_integration_platforms(
    hass: HomeAssistant,
    platform_name: str,
    # Any = platform.
    process_platform: Callable[[HomeAssistant, str, Any], Awaitable[None]],
) -> None:
    """Process a specific platform for all current and future loaded integrations."""

    async def _process(component_name: str) -> None:
        """Process component being loaded."""
        if "." in component_name:
            return

        integration = await async_get_integration(hass, component_name)

        try:
            platform = integration.get_platform(platform_name)
        except ImportError as err:
            if f"{component_name}.{platform_name}" not in str(err):
                _LOGGER.exception(
                    "Unexpected error importing %s/%s.py",
                    component_name,
                    platform_name,
                )
            return

        try:
            await process_platform(hass, component_name, platform)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Error processing platform %s.%s", component_name, platform_name
            )

    async def async_component_loaded(event: Event) -> None:
        """Handle a new component loaded."""
        await _process(event.data[ATTR_COMPONENT])

    hass.bus.async_listen(EVENT_COMPONENT_LOADED, async_component_loaded)

    tasks = [_process(comp) for comp in hass.config.components]

    if tasks:
        await asyncio.gather(*tasks)
