"""Template platform that aggregates meteorological data."""
import voluptuous as vol

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_EXCEPTIONAL,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    ATTR_CONDITION_WINDY_VARIANT,
    ENTITY_ID_FORMAT,
    WeatherEntity,
)
from homeassistant.const import CONF_NAME, CONF_UNIQUE_ID
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity import async_generate_entity_id

from .template_entity import TemplateEntity

CONDITION_CLASSES = {
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    ATTR_CONDITION_WINDY_VARIANT,
    ATTR_CONDITION_EXCEPTIONAL,
}

CONF_WEATHER = "weather"
CONF_TEMPERATURE_TEMPLATE = "temperature_template"
CONF_HUMIDITY_TEMPLATE = "humidity_template"
CONF_CONDITION_TEMPLATE = "condition_template"
CONF_ATTRIBUTION_TEMPLATE = "attribution_template"
CONF_PRESSURE_TEMPLATE = "pressure_template"
CONF_WIND_SPEED_TEMPLATE = "wind_speed_template"
CONF_WIND_BEARING_TEMPLATE = "wind_bearing_template"
CONF_OZONE_TEMPLATE = "ozone_template"
CONF_VISIBILITY_TEMPLATE = "visibility_template"
CONF_FORECAST_TEMPLATE = "forecast_template"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_CONDITION_TEMPLATE): cv.template,
        vol.Required(CONF_TEMPERATURE_TEMPLATE): cv.template,
        vol.Required(CONF_HUMIDITY_TEMPLATE): cv.template,
        vol.Optional(CONF_ATTRIBUTION_TEMPLATE): cv.template,
        vol.Optional(CONF_PRESSURE_TEMPLATE): cv.template,
        vol.Optional(CONF_WIND_SPEED_TEMPLATE): cv.template,
        vol.Optional(CONF_WIND_BEARING_TEMPLATE): cv.template,
        vol.Optional(CONF_OZONE_TEMPLATE): cv.template,
        vol.Optional(CONF_VISIBILITY_TEMPLATE): cv.template,
        vol.Optional(CONF_FORECAST_TEMPLATE): cv.template,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Template weather."""

    name = config[CONF_NAME]
    condition_template = config[CONF_CONDITION_TEMPLATE]
    temperature_template = config[CONF_TEMPERATURE_TEMPLATE]
    humidity_template = config[CONF_HUMIDITY_TEMPLATE]
    attribution_template = config.get(CONF_ATTRIBUTION_TEMPLATE)
    pressure_template = config.get(CONF_PRESSURE_TEMPLATE)
    wind_speed_template = config.get(CONF_WIND_SPEED_TEMPLATE)
    wind_bearing_template = config.get(CONF_WIND_BEARING_TEMPLATE)
    ozone_template = config.get(CONF_OZONE_TEMPLATE)
    visibility_template = config.get(CONF_VISIBILITY_TEMPLATE)
    forecast_template = config.get(CONF_FORECAST_TEMPLATE)
    unique_id = config.get(CONF_UNIQUE_ID)

    async_add_entities(
        [
            WeatherTemplate(
                hass,
                name,
                condition_template,
                temperature_template,
                humidity_template,
                attribution_template,
                pressure_template,
                wind_speed_template,
                wind_bearing_template,
                ozone_template,
                visibility_template,
                forecast_template,
                unique_id,
            )
        ]
    )


class WeatherTemplate(TemplateEntity, WeatherEntity):
    """Representation of a weather condition."""

    def __init__(
        self,
        hass,
        name,
        condition_template,
        temperature_template,
        humidity_template,
        attribution_template,
        pressure_template,
        wind_speed_template,
        wind_bearing_template,
        ozone_template,
        visibility_template,
        forecast_template,
        unique_id,
    ):
        """Initialize the Demo weather."""
        super().__init__()

        self._name = name
        self._condition_template = condition_template
        self._temperature_template = temperature_template
        self._humidity_template = humidity_template
        self._attribution_template = attribution_template
        self._pressure_template = pressure_template
        self._wind_speed_template = wind_speed_template
        self._wind_bearing_template = wind_bearing_template
        self._ozone_template = ozone_template
        self._visibility_template = visibility_template
        self._forecast_template = forecast_template
        self._unique_id = unique_id

        self.entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, name, hass=hass)

        self._condition = None
        self._temperature = None
        self._humidity = None
        self._attribution = None
        self._pressure = None
        self._wind_speed = None
        self._wind_bearing = None
        self._ozone = None
        self._visibility = None
        self._forecast = []

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def condition(self):
        """Return the current condition."""
        return self._condition

    @property
    def temperature(self):
        """Return the temperature."""
        return self._temperature

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self.hass.config.units.temperature_unit

    @property
    def humidity(self):
        """Return the humidity."""
        return self._humidity

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return self._wind_speed

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return self._wind_bearing

    @property
    def ozone(self):
        """Return the ozone level."""
        return self._ozone

    @property
    def visibility(self):
        """Return the visibility."""
        return self._visibility

    @property
    def pressure(self):
        """Return the air pressure."""
        return self._pressure

    @property
    def forecast(self):
        """Return the forecast."""
        return self._forecast

    @property
    def attribution(self):
        """Return the attribution."""
        if self._attribution is None:
            return "Powered by Home Assistant"
        return self._attribution

    @property
    def unique_id(self):
        """Return the unique id of this weather instance."""
        return self._unique_id

    async def async_added_to_hass(self):
        """Register callbacks."""

        if self._condition_template:
            self.add_template_attribute(
                "_condition",
                self._condition_template,
                lambda condition: condition if condition in CONDITION_CLASSES else None,
            )
        if self._temperature_template:
            self.add_template_attribute(
                "_temperature",
                self._temperature_template,
            )
        if self._humidity_template:
            self.add_template_attribute(
                "_humidity",
                self._humidity_template,
            )
        if self._attribution_template:
            self.add_template_attribute(
                "_attribution",
                self._attribution_template,
            )
        if self._pressure_template:
            self.add_template_attribute(
                "_pressure",
                self._pressure_template,
            )
        if self._wind_speed_template:
            self.add_template_attribute(
                "_wind_speed",
                self._wind_speed_template,
            )
        if self._wind_bearing_template:
            self.add_template_attribute(
                "_wind_bearing",
                self._wind_bearing_template,
            )
        if self._ozone_template:
            self.add_template_attribute(
                "_ozone",
                self._ozone_template,
            )
        if self._visibility_template:
            self.add_template_attribute(
                "_visibility",
                self._visibility_template,
            )
        if self._forecast_template:
            self.add_template_attribute(
                "_forecast",
                self._forecast_template,
            )
        await super().async_added_to_hass()
