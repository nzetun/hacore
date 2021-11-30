"""Fixtures for the AVM Fritz!Box integration."""
from unittest.mock import Mock, patch

import pytest


@pytest.fixture(name="fritz")
def fritz_fixture() -> Mock:
    """Patch libraries."""
    with patch("homeassistant.components.fritzbox.Fritzhome") as fritz, patch(
        "homeassistant.components.fritzbox.config_flow.Fritzhome"
    ):
        yield fritz
