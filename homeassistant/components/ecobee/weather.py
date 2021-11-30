"""Support for displaying weather info from Ecobee API."""
from __future__ import annotations

from datetime import timedelta

from pyecobee.const import ECOBEE_STATE_UNKNOWN

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    WeatherEntity,
)
from homeassistant.const import PRESSURE_HPA, PRESSURE_INHG, TEMP_FAHRENHEIT
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import dt as dt_util
from homeassistant.util.pressure import convert as pressure_convert

from .const import (
    DOMAIN,
    ECOBEE_MODEL_TO_NAME,
    ECOBEE_WEATHER_SYMBOL_TO_HASS,
    MANUFACTURER,
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the ecobee weather platform."""
    data = hass.data[DOMAIN]
    dev = []
    for index in range(len(data.ecobee.thermostats)):
        thermostat = data.ecobee.get_thermostat(index)
        if "weather" in thermostat:
            dev.append(EcobeeWeather(data, thermostat["name"], index))

    async_add_entities(dev, True)


class EcobeeWeather(WeatherEntity):
    """Representation of Ecobee weather data."""

    def __init__(self, data, name, index):
        """Initialize the Ecobee weather platform."""
        self.data = data
        self._name = name
        self._index = index
        self.weather = None

    def get_forecast(self, index, param):
        """Retrieve forecast parameter."""
        try:
            forecast = self.weather["forecasts"][index]
            return forecast[param]
        except (IndexError, KeyError) as err:
            raise ValueError from err

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique identifier for the weather platform."""
        return self.data.ecobee.get_thermostat(self._index)["identifier"]

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the ecobee weather platform."""
        thermostat = self.data.ecobee.get_thermostat(self._index)
        model: str | None
        try:
            model = f"{ECOBEE_MODEL_TO_NAME[thermostat['modelNumber']]} Thermostat"
        except KeyError:
            # Ecobee model is not in our list
            model = None

        return DeviceInfo(
            identifiers={(DOMAIN, thermostat["identifier"])},
            manufacturer=MANUFACTURER,
            model=model,
            name=self.name,
        )

    @property
    def condition(self):
        """Return the current condition."""
        try:
            return ECOBEE_WEATHER_SYMBOL_TO_HASS[self.get_forecast(0, "weatherSymbol")]
        except ValueError:
            return None

    @property
    def temperature(self):
        """Return the temperature."""
        try:
            return float(self.get_forecast(0, "temperature")) / 10
        except ValueError:
            return None

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT

    @property
    def pressure(self):
        """Return the pressure."""
        try:
            pressure = self.get_forecast(0, "pressure")
            if not self.hass.config.units.is_metric:
                pressure = pressure_convert(pressure, PRESSURE_HPA, PRESSURE_INHG)
                return round(pressure, 2)
            return round(pressure)
        except ValueError:
            return None

    @property
    def humidity(self):
        """Return the humidity."""
        try:
            return int(self.get_forecast(0, "relativeHumidity"))
        except ValueError:
            return None

    @property
    def visibility(self):
        """Return the visibility."""
        try:
            return int(self.get_forecast(0, "visibility")) / 1000
        except ValueError:
            return None

    @property
    def wind_speed(self):
        """Return the wind speed."""
        try:
            return int(self.get_forecast(0, "windSpeed"))
        except ValueError:
            return None

    @property
    def wind_bearing(self):
        """Return the wind direction."""
        try:
            return int(self.get_forecast(0, "windBearing"))
        except ValueError:
            return None

    @property
    def attribution(self):
        """Return the attribution."""
        if not self.weather:
            return None

        station = self.weather.get("weatherStation", "UNKNOWN")
        time = self.weather.get("timestamp", "UNKNOWN")
        return f"Ecobee weather provided by {station} at {time} UTC"

    @property
    def forecast(self):
        """Return the forecast array."""
        if "forecasts" not in self.weather:
            return None

        forecasts = []
        date = dt_util.utcnow()
        for day in range(0, 5):
            forecast = _process_forecast(self.weather["forecasts"][day])
            if forecast is None:
                continue
            forecast[ATTR_FORECAST_TIME] = date.isoformat()
            date += timedelta(days=1)
            forecasts.append(forecast)

        if forecasts:
            return forecasts
        return None

    async def async_update(self):
        """Get the latest weather data."""
        await self.data.update()
        thermostat = self.data.ecobee.get_thermostat(self._index)
        self.weather = thermostat.get("weather")


def _process_forecast(json):
    """Process a single ecobee API forecast to return expected values."""
    forecast = {}
    try:
        forecast[ATTR_FORECAST_CONDITION] = ECOBEE_WEATHER_SYMBOL_TO_HASS[
            json["weatherSymbol"]
        ]
        if json["tempHigh"] != ECOBEE_STATE_UNKNOWN:
            forecast[ATTR_FORECAST_TEMP] = float(json["tempHigh"]) / 10
        if json["tempLow"] != ECOBEE_STATE_UNKNOWN:
            forecast[ATTR_FORECAST_TEMP_LOW] = float(json["tempLow"]) / 10
        if json["windBearing"] != ECOBEE_STATE_UNKNOWN:
            forecast[ATTR_FORECAST_WIND_BEARING] = int(json["windBearing"])
        if json["windSpeed"] != ECOBEE_STATE_UNKNOWN:
            forecast[ATTR_FORECAST_WIND_SPEED] = int(json["windSpeed"])

    except (ValueError, IndexError, KeyError):
        return None

    if forecast:
        return forecast
    return None
