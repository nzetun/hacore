"""Support for Template lights."""
import logging

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ATTR_WHITE_VALUE,
    ENTITY_ID_FORMAT,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_EFFECT,
    SUPPORT_TRANSITION,
    SUPPORT_WHITE_VALUE,
    LightEntity,
)
from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_ENTITY_PICTURE_TEMPLATE,
    CONF_FRIENDLY_NAME,
    CONF_ICON_TEMPLATE,
    CONF_LIGHTS,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.script import Script

from .const import CONF_AVAILABILITY_TEMPLATE, DOMAIN
from .template_entity import TemplateEntity

_LOGGER = logging.getLogger(__name__)
_VALID_STATES = [STATE_ON, STATE_OFF, "true", "false"]

CONF_ON_ACTION = "turn_on"
CONF_OFF_ACTION = "turn_off"
CONF_LEVEL_ACTION = "set_level"
CONF_LEVEL_TEMPLATE = "level_template"
CONF_TEMPERATURE_TEMPLATE = "temperature_template"
CONF_TEMPERATURE_ACTION = "set_temperature"
CONF_COLOR_TEMPLATE = "color_template"
CONF_COLOR_ACTION = "set_color"
CONF_WHITE_VALUE_TEMPLATE = "white_value_template"
CONF_WHITE_VALUE_ACTION = "set_white_value"
CONF_EFFECT_ACTION = "set_effect"
CONF_EFFECT_LIST_TEMPLATE = "effect_list_template"
CONF_EFFECT_TEMPLATE = "effect_template"
CONF_MAX_MIREDS_TEMPLATE = "max_mireds_template"
CONF_MIN_MIREDS_TEMPLATE = "min_mireds_template"
CONF_SUPPORTS_TRANSITION = "supports_transition_template"

LIGHT_SCHEMA = vol.All(
    cv.deprecated(CONF_ENTITY_ID),
    vol.Schema(
        {
            vol.Required(CONF_ON_ACTION): cv.SCRIPT_SCHEMA,
            vol.Required(CONF_OFF_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_ICON_TEMPLATE): cv.template,
            vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
            vol.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
            vol.Optional(CONF_LEVEL_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_LEVEL_TEMPLATE): cv.template,
            vol.Optional(CONF_FRIENDLY_NAME): cv.string,
            vol.Optional(CONF_ENTITY_ID): cv.entity_ids,
            vol.Optional(CONF_TEMPERATURE_TEMPLATE): cv.template,
            vol.Optional(CONF_TEMPERATURE_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_COLOR_TEMPLATE): cv.template,
            vol.Optional(CONF_COLOR_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_WHITE_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_WHITE_VALUE_ACTION): cv.SCRIPT_SCHEMA,
            vol.Inclusive(CONF_EFFECT_LIST_TEMPLATE, "effect"): cv.template,
            vol.Inclusive(CONF_EFFECT_TEMPLATE, "effect"): cv.template,
            vol.Inclusive(CONF_EFFECT_ACTION, "effect"): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_MAX_MIREDS_TEMPLATE): cv.template,
            vol.Optional(CONF_MIN_MIREDS_TEMPLATE): cv.template,
            vol.Optional(CONF_SUPPORTS_TRANSITION): cv.template,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    ),
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_LIGHTS): cv.schema_with_slug_keys(LIGHT_SCHEMA)}
)


async def _async_create_entities(hass, config):
    """Create the Template Lights."""
    lights = []

    for device, device_config in config[CONF_LIGHTS].items():
        friendly_name = device_config.get(CONF_FRIENDLY_NAME, device)

        state_template = device_config.get(CONF_VALUE_TEMPLATE)
        icon_template = device_config.get(CONF_ICON_TEMPLATE)
        entity_picture_template = device_config.get(CONF_ENTITY_PICTURE_TEMPLATE)
        availability_template = device_config.get(CONF_AVAILABILITY_TEMPLATE)
        unique_id = device_config.get(CONF_UNIQUE_ID)

        on_action = device_config[CONF_ON_ACTION]
        off_action = device_config[CONF_OFF_ACTION]

        level_action = device_config.get(CONF_LEVEL_ACTION)
        level_template = device_config.get(CONF_LEVEL_TEMPLATE)

        temperature_action = device_config.get(CONF_TEMPERATURE_ACTION)
        temperature_template = device_config.get(CONF_TEMPERATURE_TEMPLATE)

        color_action = device_config.get(CONF_COLOR_ACTION)
        color_template = device_config.get(CONF_COLOR_TEMPLATE)

        white_value_action = device_config.get(CONF_WHITE_VALUE_ACTION)
        white_value_template = device_config.get(CONF_WHITE_VALUE_TEMPLATE)

        effect_action = device_config.get(CONF_EFFECT_ACTION)
        effect_list_template = device_config.get(CONF_EFFECT_LIST_TEMPLATE)
        effect_template = device_config.get(CONF_EFFECT_TEMPLATE)

        max_mireds_template = device_config.get(CONF_MAX_MIREDS_TEMPLATE)
        min_mireds_template = device_config.get(CONF_MIN_MIREDS_TEMPLATE)

        supports_transition_template = device_config.get(CONF_SUPPORTS_TRANSITION)

        lights.append(
            LightTemplate(
                hass,
                device,
                friendly_name,
                state_template,
                icon_template,
                entity_picture_template,
                availability_template,
                on_action,
                off_action,
                level_action,
                level_template,
                temperature_action,
                temperature_template,
                color_action,
                color_template,
                white_value_action,
                white_value_template,
                effect_action,
                effect_list_template,
                effect_template,
                max_mireds_template,
                min_mireds_template,
                supports_transition_template,
                unique_id,
            )
        )

    return lights


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the template lights."""
    async_add_entities(await _async_create_entities(hass, config))


class LightTemplate(TemplateEntity, LightEntity):
    """Representation of a templated Light, including dimmable."""

    def __init__(
        self,
        hass,
        device_id,
        friendly_name,
        state_template,
        icon_template,
        entity_picture_template,
        availability_template,
        on_action,
        off_action,
        level_action,
        level_template,
        temperature_action,
        temperature_template,
        color_action,
        color_template,
        white_value_action,
        white_value_template,
        effect_action,
        effect_list_template,
        effect_template,
        max_mireds_template,
        min_mireds_template,
        supports_transition_template,
        unique_id,
    ):
        """Initialize the light."""
        super().__init__(
            availability_template=availability_template,
            icon_template=icon_template,
            entity_picture_template=entity_picture_template,
        )
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass
        )
        self._name = friendly_name
        self._template = state_template
        self._on_script = Script(hass, on_action, friendly_name, DOMAIN)
        self._off_script = Script(hass, off_action, friendly_name, DOMAIN)
        self._level_script = None
        if level_action is not None:
            self._level_script = Script(hass, level_action, friendly_name, DOMAIN)
        self._level_template = level_template
        self._temperature_script = None
        if temperature_action is not None:
            self._temperature_script = Script(
                hass, temperature_action, friendly_name, DOMAIN
            )
        self._temperature_template = temperature_template
        self._color_script = None
        if color_action is not None:
            self._color_script = Script(hass, color_action, friendly_name, DOMAIN)
        self._color_template = color_template
        self._white_value_script = None
        if white_value_action is not None:
            self._white_value_script = Script(
                hass, white_value_action, friendly_name, DOMAIN
            )
        self._white_value_template = white_value_template
        self._effect_script = None
        if effect_action is not None:
            self._effect_script = Script(hass, effect_action, friendly_name, DOMAIN)
        self._effect_list_template = effect_list_template
        self._effect_template = effect_template
        self._max_mireds_template = max_mireds_template
        self._min_mireds_template = min_mireds_template
        self._supports_transition_template = supports_transition_template

        self._state = False
        self._brightness = None
        self._temperature = None
        self._color = None
        self._white_value = None
        self._effect = None
        self._effect_list = None
        self._max_mireds = None
        self._min_mireds = None
        self._supports_transition = False
        self._unique_id = unique_id

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def color_temp(self):
        """Return the CT color value in mireds."""
        return self._temperature

    @property
    def max_mireds(self):
        """Return the max mireds value in mireds."""
        if self._max_mireds is not None:
            return self._max_mireds

        return super().max_mireds

    @property
    def min_mireds(self):
        """Return the min mireds value in mireds."""
        if self._min_mireds is not None:
            return self._min_mireds

        return super().min_mireds

    @property
    def white_value(self):
        """Return the white value."""
        return self._white_value

    @property
    def hs_color(self):
        """Return the hue and saturation color value [float, float]."""
        return self._color

    @property
    def effect(self):
        """Return the effect."""
        return self._effect

    @property
    def effect_list(self):
        """Return the effect list."""
        return self._effect_list

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of this light."""
        return self._unique_id

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = 0
        if self._level_script is not None:
            supported_features |= SUPPORT_BRIGHTNESS
        if self._temperature_script is not None:
            supported_features |= SUPPORT_COLOR_TEMP
        if self._color_script is not None:
            supported_features |= SUPPORT_COLOR
        if self._white_value_script is not None:
            supported_features |= SUPPORT_WHITE_VALUE
        if self._effect_script is not None:
            supported_features |= SUPPORT_EFFECT
        if self._supports_transition is True:
            supported_features |= SUPPORT_TRANSITION
        return supported_features

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    async def async_added_to_hass(self):
        """Register callbacks."""
        if self._template:
            self.add_template_attribute(
                "_state", self._template, None, self._update_state
            )
        if self._level_template:
            self.add_template_attribute(
                "_brightness",
                self._level_template,
                None,
                self._update_brightness,
                none_on_template_error=True,
            )
        if self._max_mireds_template:
            self.add_template_attribute(
                "_max_mireds_template",
                self._max_mireds_template,
                None,
                self._update_max_mireds,
                none_on_template_error=True,
            )
        if self._min_mireds_template:
            self.add_template_attribute(
                "_min_mireds_template",
                self._min_mireds_template,
                None,
                self._update_min_mireds,
                none_on_template_error=True,
            )
        if self._temperature_template:
            self.add_template_attribute(
                "_temperature",
                self._temperature_template,
                None,
                self._update_temperature,
                none_on_template_error=True,
            )
        if self._color_template:
            self.add_template_attribute(
                "_color",
                self._color_template,
                None,
                self._update_color,
                none_on_template_error=True,
            )
        if self._white_value_template:
            self.add_template_attribute(
                "_white_value",
                self._white_value_template,
                None,
                self._update_white_value,
                none_on_template_error=True,
            )
        if self._effect_list_template:
            self.add_template_attribute(
                "_effect_list",
                self._effect_list_template,
                None,
                self._update_effect_list,
                none_on_template_error=True,
            )
        if self._effect_template:
            self.add_template_attribute(
                "_effect",
                self._effect_template,
                None,
                self._update_effect,
                none_on_template_error=True,
            )
        if self._supports_transition_template:
            self.add_template_attribute(
                "_supports_transition_template",
                self._supports_transition_template,
                None,
                self._update_supports_transition,
                none_on_template_error=True,
            )
        await super().async_added_to_hass()

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        optimistic_set = False
        # set optimistic states
        if self._template is None:
            self._state = True
            optimistic_set = True

        if self._level_template is None and ATTR_BRIGHTNESS in kwargs:
            _LOGGER.info(
                "Optimistically setting brightness to %s", kwargs[ATTR_BRIGHTNESS]
            )
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            optimistic_set = True

        if self._white_value_template is None and ATTR_WHITE_VALUE in kwargs:
            _LOGGER.info(
                "Optimistically setting white value to %s", kwargs[ATTR_WHITE_VALUE]
            )
            self._white_value = kwargs[ATTR_WHITE_VALUE]
            optimistic_set = True

        if self._temperature_template is None and ATTR_COLOR_TEMP in kwargs:
            _LOGGER.info(
                "Optimistically setting color temperature to %s",
                kwargs[ATTR_COLOR_TEMP],
            )
            self._temperature = kwargs[ATTR_COLOR_TEMP]
            optimistic_set = True

        common_params = {}

        if ATTR_BRIGHTNESS in kwargs:
            common_params["brightness"] = kwargs[ATTR_BRIGHTNESS]

        if ATTR_TRANSITION in kwargs and self._supports_transition is True:
            common_params["transition"] = kwargs[ATTR_TRANSITION]

        if ATTR_COLOR_TEMP in kwargs and self._temperature_script:
            common_params["color_temp"] = kwargs[ATTR_COLOR_TEMP]

            await self._temperature_script.async_run(
                common_params, context=self._context
            )
        elif ATTR_WHITE_VALUE in kwargs and self._white_value_script:
            common_params["white_value"] = kwargs[ATTR_WHITE_VALUE]

            await self._white_value_script.async_run(
                common_params, context=self._context
            )
        elif ATTR_EFFECT in kwargs and self._effect_script:
            effect = kwargs[ATTR_EFFECT]
            if effect not in self._effect_list:
                _LOGGER.error(
                    "Received invalid effect: %s. Expected one of: %s",
                    effect,
                    self._effect_list,
                    exc_info=True,
                )

            common_params["effect"] = effect

            await self._effect_script.async_run(common_params, context=self._context)
        elif ATTR_HS_COLOR in kwargs and self._color_script:
            hs_value = kwargs[ATTR_HS_COLOR]
            common_params["hs"] = hs_value
            common_params["h"] = int(hs_value[0])
            common_params["s"] = int(hs_value[1])

            await self._color_script.async_run(
                common_params,
                context=self._context,
            )
        elif ATTR_BRIGHTNESS in kwargs and self._level_script:
            await self._level_script.async_run(common_params, context=self._context)
        else:
            await self._on_script.async_run(common_params, context=self._context)

        if optimistic_set:
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        if ATTR_TRANSITION in kwargs and self._supports_transition is True:
            await self._off_script.async_run(
                {"transition": kwargs[ATTR_TRANSITION]}, context=self._context
            )
        else:
            await self._off_script.async_run(context=self._context)
        if self._template is None:
            self._state = False
            self.async_write_ha_state()

    @callback
    def _update_brightness(self, brightness):
        """Update the brightness from the template."""
        try:
            if brightness in (None, "None", ""):
                self._brightness = None
                return
            if 0 <= int(brightness) <= 255:
                self._brightness = int(brightness)
            else:
                _LOGGER.error(
                    "Received invalid brightness : %s. Expected: 0-255", brightness
                )
                self._brightness = None
        except ValueError:
            _LOGGER.error(
                "Template must supply an integer brightness from 0-255, or 'None'",
                exc_info=True,
            )
            self._brightness = None

    @callback
    def _update_white_value(self, white_value):
        """Update the white value from the template."""
        try:
            if white_value in (None, "None", ""):
                self._white_value = None
                return
            if 0 <= int(white_value) <= 255:
                self._white_value = int(white_value)
            else:
                _LOGGER.error(
                    "Received invalid white value: %s. Expected: 0-255", white_value
                )
                self._white_value = None
        except ValueError:
            _LOGGER.error(
                "Template must supply an integer white_value from 0-255, or 'None'",
                exc_info=True,
            )
            self._white_value = None

    @callback
    def _update_effect_list(self, effect_list):
        """Update the effect list from the template."""
        if effect_list in (None, "None", ""):
            self._effect_list = None
            return

        if not isinstance(effect_list, list):
            _LOGGER.error(
                "Received invalid effect list: %s. Expected list of strings",
                effect_list,
            )
            self._effect_list = None
            return

        if len(effect_list) == 0:
            self._effect_list = None
            return

        self._effect_list = effect_list

    @callback
    def _update_effect(self, effect):
        """Update the effect from the template."""
        if effect in (None, "None", ""):
            self._effect = None
            return

        if effect not in self._effect_list:
            _LOGGER.error(
                "Received invalid effect: %s. Expected one of: %s",
                effect,
                self._effect_list,
            )
            self._effect = None
            return

        self._effect = effect

    @callback
    def _update_state(self, result):
        """Update the state from the template."""
        if isinstance(result, TemplateError):
            # This behavior is legacy
            self._state = False
            if not self._availability_template:
                self._attr_available = True
            return

        if isinstance(result, bool):
            self._state = result
            return

        state = str(result).lower()
        if state in _VALID_STATES:
            self._state = state in ("true", STATE_ON)
            return

        _LOGGER.error(
            "Received invalid light is_on state: %s. Expected: %s",
            state,
            ", ".join(_VALID_STATES),
        )
        self._state = None

    @callback
    def _update_temperature(self, render):
        """Update the temperature from the template."""
        try:
            if render in (None, "None", ""):
                self._temperature = None
                return
            temperature = int(render)
            if self.min_mireds <= temperature <= self.max_mireds:
                self._temperature = temperature
            else:
                _LOGGER.error(
                    "Received invalid color temperature : %s. Expected: %s-%s",
                    temperature,
                    self.min_mireds,
                    self.max_mireds,
                )
                self._temperature = None
        except ValueError:
            _LOGGER.error(
                "Template must supply an integer temperature within the range for this light, or 'None'",
                exc_info=True,
            )
            self._temperature = None

    @callback
    def _update_color(self, render):
        """Update the hs_color from the template."""
        h_str = s_str = None
        if isinstance(render, str):
            if render in (None, "None", ""):
                self._color = None
                return
            h_str, s_str = map(
                float, render.replace("(", "").replace(")", "").split(",", 1)
            )
        elif isinstance(render, (list, tuple)) and len(render) == 2:
            h_str, s_str = render

        if (
            h_str is not None
            and s_str is not None
            and 0 <= h_str <= 360
            and 0 <= s_str <= 100
        ):
            self._color = (h_str, s_str)
        elif h_str is not None and s_str is not None:
            _LOGGER.error(
                "Received invalid hs_color : (%s, %s). Expected: (0-360, 0-100)",
                h_str,
                s_str,
            )
            self._color = None
        else:
            _LOGGER.error("Received invalid hs_color : (%s)", render)
            self._color = None

    @callback
    def _update_max_mireds(self, render):
        """Update the max mireds from the template."""

        try:
            if render in (None, "None", ""):
                self._max_mireds = None
                return
            self._max_mireds = int(render)
        except ValueError:
            _LOGGER.error(
                "Template must supply an integer temperature within the range for this light, or 'None'",
                exc_info=True,
            )
            self._max_mireds = None

    @callback
    def _update_min_mireds(self, render):
        """Update the min mireds from the template."""
        try:
            if render in (None, "None", ""):
                self._min_mireds = None
                return
            self._min_mireds = int(render)
        except ValueError:
            _LOGGER.error(
                "Template must supply an integer temperature within the range for this light, or 'None'",
                exc_info=True,
            )
            self._min_mireds = None

    @callback
    def _update_supports_transition(self, render):
        """Update the supports transition from the template."""
        if render in (None, "None", ""):
            self._supports_transition = False
            return
        self._supports_transition = bool(render)
