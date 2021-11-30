"""Ask tankerkoenig.de for petrol price information."""
from datetime import timedelta
import logging
from math import ceil

import pytankerkoenig
import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    CONF_SHOW_ON_MAP,
)
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform

from .const import CONF_FUEL_TYPES, CONF_STATIONS, DOMAIN, FUEL_TYPES

_LOGGER = logging.getLogger(__name__)

DEFAULT_RADIUS = 2
DEFAULT_SCAN_INTERVAL = timedelta(minutes=30)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_API_KEY): cv.string,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): cv.time_period,
                vol.Optional(CONF_FUEL_TYPES, default=FUEL_TYPES): vol.All(
                    cv.ensure_list, [vol.In(FUEL_TYPES)]
                ),
                vol.Inclusive(
                    CONF_LATITUDE,
                    "coordinates",
                    "Latitude and longitude must exist together",
                ): cv.latitude,
                vol.Inclusive(
                    CONF_LONGITUDE,
                    "coordinates",
                    "Latitude and longitude must exist together",
                ): cv.longitude,
                vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS): vol.All(
                    cv.positive_int, vol.Range(min=1)
                ),
                vol.Optional(CONF_STATIONS, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
                vol.Optional(CONF_SHOW_ON_MAP, default=True): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set the tankerkoenig component up."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    _LOGGER.debug("Setting up integration")

    tankerkoenig = TankerkoenigData(hass, conf)

    latitude = conf.get(CONF_LATITUDE, hass.config.latitude)
    longitude = conf.get(CONF_LONGITUDE, hass.config.longitude)
    radius = conf[CONF_RADIUS]
    additional_stations = conf[CONF_STATIONS]

    setup_ok = await hass.async_add_executor_job(
        tankerkoenig.setup, latitude, longitude, radius, additional_stations
    )
    if not setup_ok:
        _LOGGER.error("Could not setup integration")
        return False

    hass.data[DOMAIN] = tankerkoenig

    hass.async_create_task(
        async_load_platform(
            hass,
            SENSOR_DOMAIN,
            DOMAIN,
            discovered=tankerkoenig.stations,
            hass_config=conf,
        )
    )

    return True


class TankerkoenigData:
    """Get the latest data from the API."""

    def __init__(self, hass, conf):
        """Initialize the data object."""
        self._api_key = conf[CONF_API_KEY]
        self.stations = {}
        self.fuel_types = conf[CONF_FUEL_TYPES]
        self.update_interval = conf[CONF_SCAN_INTERVAL]
        self.show_on_map = conf[CONF_SHOW_ON_MAP]
        self._hass = hass

    def setup(self, latitude, longitude, radius, additional_stations):
        """Set up the tankerkoenig API.

        Read the initial data from the server, to initialize the list of fuel stations to monitor.
        """
        _LOGGER.debug("Fetching data for (%s, %s) rad: %s", latitude, longitude, radius)
        try:
            data = pytankerkoenig.getNearbyStations(
                self._api_key, latitude, longitude, radius, "all", "dist"
            )
        except pytankerkoenig.customException as err:
            data = {"ok": False, "message": err, "exception": True}
        _LOGGER.debug("Received data: %s", data)
        if not data["ok"]:
            _LOGGER.error(
                "Setup for sensors was unsuccessful. Error occurred while fetching data from tankerkoenig.de: %s",
                data["message"],
            )
            return False

        # Add stations found via location + radius
        if not (nearby_stations := data["stations"]):
            if not additional_stations:
                _LOGGER.error(
                    "Could not find any station in range."
                    "Try with a bigger radius or manually specify stations in additional_stations"
                )
                return False
            _LOGGER.warning(
                "Could not find any station in range. Will only use manually specified stations"
            )
        else:
            for station in nearby_stations:
                self.add_station(station)

        # Add manually specified additional stations
        for station_id in additional_stations:
            try:
                additional_station_data = pytankerkoenig.getStationData(
                    self._api_key, station_id
                )
            except pytankerkoenig.customException as err:
                additional_station_data = {
                    "ok": False,
                    "message": err,
                    "exception": True,
                }

            if not additional_station_data["ok"]:
                _LOGGER.error(
                    "Error when adding station %s:\n %s",
                    station_id,
                    additional_station_data["message"],
                )
                return False
            self.add_station(additional_station_data["station"])
        if len(self.stations) > 10:
            _LOGGER.warning(
                "Found more than 10 stations to check. "
                "This might invalidate your api-key on the long run. "
                "Try using a smaller radius"
            )
        return True

    async def fetch_data(self):
        """Get the latest data from tankerkoenig.de."""
        _LOGGER.debug("Fetching new data from tankerkoenig.de")
        station_ids = list(self.stations)

        prices = {}

        # The API seems to only return at most 10 results, so split the list in chunks of 10
        # and merge it together.
        for index in range(ceil(len(station_ids) / 10)):
            data = await self._hass.async_add_executor_job(
                pytankerkoenig.getPriceList,
                self._api_key,
                station_ids[index * 10 : (index + 1) * 10],
            )

            _LOGGER.debug("Received data: %s", data)
            if not data["ok"]:
                _LOGGER.error(
                    "Error fetching data from tankerkoenig.de: %s", data["message"]
                )
                raise TankerkoenigError(data["message"])
            if "prices" not in data:
                _LOGGER.error("Did not receive price information from tankerkoenig.de")
                raise TankerkoenigError("No prices in data")
            prices.update(data["prices"])
        return prices

    def add_station(self, station: dict):
        """Add fuel station to the entity list."""
        station_id = station["id"]
        if station_id in self.stations:
            _LOGGER.warning(
                "Sensor for station with id %s was already created", station_id
            )
            return

        self.stations[station_id] = station
        _LOGGER.debug("add_station called for station: %s", station)


class TankerkoenigError(HomeAssistantError):
    """An error occurred while contacting tankerkoenig.de."""
