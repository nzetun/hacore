"""Provides the constants needed for the component."""

from typing import Final

ATTR_VALUE = "value"
ATTR_MIN = "min"
ATTR_MAX = "max"
ATTR_STEP = "step"

MODE_AUTO: Final = "auto"
MODE_BOX: Final = "box"
MODE_SLIDER: Final = "slider"

DEFAULT_MIN_VALUE = 0.0
DEFAULT_MAX_VALUE = 100.0
DEFAULT_STEP = 1.0

DOMAIN = "number"

SERVICE_SET_VALUE = "set_value"
