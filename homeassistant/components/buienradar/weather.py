"""Support for Buienradar.nl weather service."""
import logging

from buienradar.constants import (
    CONDCODE,
    CONDITION,
    DATETIME,
    MAX_TEMP,
    MIN_TEMP,
    RAIN,
    WINDAZIMUTH,
    WINDSPEED,
)

from homeassistant.components.weather import (
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
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    WeatherEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

# Reuse data and API logic from the sensor implementation
from .const import DEFAULT_TIMEFRAME, DOMAIN
from .util import BrData

_LOGGER = logging.getLogger(__name__)

CONF_FORECAST = "forecast"

DATA_CONDITION = "buienradar_condition"

CONDITION_CLASSES = {
    ATTR_CONDITION_CLOUDY: ("c", "p"),
    ATTR_CONDITION_FOG: ("d", "n"),
    ATTR_CONDITION_HAIL: (),
    ATTR_CONDITION_LIGHTNING: ("g",),
    ATTR_CONDITION_LIGHTNING_RAINY: ("s",),
    ATTR_CONDITION_PARTLYCLOUDY: (
        "b",
        "j",
        "o",
        "r",
    ),
    ATTR_CONDITION_POURING: ("l", "q"),
    ATTR_CONDITION_RAINY: ("f", "h", "k", "m"),
    ATTR_CONDITION_SNOWY: ("u", "i", "v", "t"),
    ATTR_CONDITION_SNOWY_RAINY: ("w",),
    ATTR_CONDITION_SUNNY: ("a",),
    ATTR_CONDITION_WINDY: (),
    ATTR_CONDITION_WINDY_VARIANT: (),
    ATTR_CONDITION_EXCEPTIONAL: (),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the buienradar platform."""
    config = entry.data

    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)

    if None in (latitude, longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return

    coordinates = {CONF_LATITUDE: float(latitude), CONF_LONGITUDE: float(longitude)}

    # create weather data:
    data = BrData(hass, coordinates, DEFAULT_TIMEFRAME, None)
    # create weather device:
    _LOGGER.debug("Initializing buienradar weather: coordinates %s", coordinates)

    # create condition helper
    if DATA_CONDITION not in hass.data[DOMAIN]:
        cond_keys = [str(chr(x)) for x in range(97, 123)]
        hass.data[DOMAIN][DATA_CONDITION] = dict.fromkeys(cond_keys)
        for cond, condlst in CONDITION_CLASSES.items():
            for condi in condlst:
                hass.data[DOMAIN][DATA_CONDITION][condi] = cond

    async_add_entities([BrWeather(data, config, coordinates)])

    # schedule the first update in 1 minute from now:
    await data.schedule_update(1)


class BrWeather(WeatherEntity):
    """Representation of a weather condition."""

    _attr_temperature_unit = TEMP_CELSIUS

    def __init__(self, data, config, coordinates):
        """Initialize the platform with a data instance and station name."""
        self._stationname = config.get(CONF_NAME, "Buienradar")
        self._attr_name = (
            self._stationname or f"BR {data.stationname or '(unknown station)'}"
        )
        self._data = data

        self._attr_unique_id = "{:2.6f}{:2.6f}".format(
            coordinates[CONF_LATITUDE], coordinates[CONF_LONGITUDE]
        )

    @property
    def attribution(self):
        """Return the attribution."""
        return self._data.attribution

    @property
    def condition(self):
        """Return the current condition."""
        if (
            self._data
            and self._data.condition
            and (ccode := self._data.condition.get(CONDCODE))
            and (conditions := self.hass.data[DOMAIN].get(DATA_CONDITION))
        ):
            return conditions.get(ccode)

    @property
    def temperature(self):
        """Return the current temperature."""
        return self._data.temperature

    @property
    def pressure(self):
        """Return the current pressure."""
        return self._data.pressure

    @property
    def humidity(self):
        """Return the name of the sensor."""
        return self._data.humidity

    @property
    def visibility(self):
        """Return the current visibility in km."""
        if self._data.visibility is None:
            return None
        return round(self._data.visibility / 1000, 1)

    @property
    def wind_speed(self):
        """Return the current windspeed in km/h."""
        if self._data.wind_speed is None:
            return None
        return round(self._data.wind_speed * 3.6, 1)

    @property
    def wind_bearing(self):
        """Return the current wind bearing (degrees)."""
        return self._data.wind_bearing

    @property
    def forecast(self):
        """Return the forecast array."""
        fcdata_out = []
        cond = self.hass.data[DOMAIN][DATA_CONDITION]

        if not self._data.forecast:
            return None

        for data_in in self._data.forecast:
            # remap keys from external library to
            # keys understood by the weather component:
            condcode = data_in.get(CONDITION, []).get(CONDCODE)
            data_out = {
                ATTR_FORECAST_TIME: data_in.get(DATETIME).isoformat(),
                ATTR_FORECAST_CONDITION: cond[condcode],
                ATTR_FORECAST_TEMP_LOW: data_in.get(MIN_TEMP),
                ATTR_FORECAST_TEMP: data_in.get(MAX_TEMP),
                ATTR_FORECAST_PRECIPITATION: data_in.get(RAIN),
                ATTR_FORECAST_WIND_BEARING: data_in.get(WINDAZIMUTH),
                ATTR_FORECAST_WIND_SPEED: round(data_in.get(WINDSPEED) * 3.6, 1),
            }

            fcdata_out.append(data_out)

        return fcdata_out
