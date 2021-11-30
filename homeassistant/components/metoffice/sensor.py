"""Support for UK Met Office weather service."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    LENGTH_KILOMETERS,
    PERCENTAGE,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
    UV_INDEX,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import get_device_info
from .const import (
    ATTRIBUTION,
    CONDITION_CLASSES,
    DOMAIN,
    METOFFICE_COORDINATES,
    METOFFICE_DAILY_COORDINATOR,
    METOFFICE_HOURLY_COORDINATOR,
    METOFFICE_NAME,
    MODE_3HOURLY_LABEL,
    MODE_DAILY,
    MODE_DAILY_LABEL,
    VISIBILITY_CLASSES,
    VISIBILITY_DISTANCE_CLASSES,
)

ATTR_LAST_UPDATE = "last_update"
ATTR_SENSOR_ID = "sensor_id"
ATTR_SITE_ID = "site_id"
ATTR_SITE_NAME = "site_name"


SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="name",
        name="Station Name",
        device_class=None,
        native_unit_of_measurement=None,
        icon="mdi:label-outline",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="weather",
        name="Weather",
        device_class=None,
        native_unit_of_measurement=None,
        icon="mdi:weather-sunny",  # but will adapt to current conditions
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        icon=None,
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="feels_like_temperature",
        name="Feels Like Temperature",
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        icon=None,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="wind_speed",
        name="Wind Speed",
        device_class=None,
        native_unit_of_measurement=SPEED_MILES_PER_HOUR,
        icon="mdi:weather-windy",
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="wind_direction",
        name="Wind Direction",
        device_class=None,
        native_unit_of_measurement=None,
        icon="mdi:compass-outline",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="wind_gust",
        name="Wind Gust",
        device_class=None,
        native_unit_of_measurement=SPEED_MILES_PER_HOUR,
        icon="mdi:weather-windy",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="visibility",
        name="Visibility",
        device_class=None,
        native_unit_of_measurement=None,
        icon="mdi:eye",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="visibility_distance",
        name="Visibility Distance",
        device_class=None,
        native_unit_of_measurement=LENGTH_KILOMETERS,
        icon="mdi:eye",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="uv",
        name="UV Index",
        device_class=None,
        native_unit_of_measurement=UV_INDEX,
        icon="mdi:weather-sunny-alert",
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="precipitation",
        name="Probability of Precipitation",
        device_class=None,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:weather-rainy",
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        device_class=DEVICE_CLASS_HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        icon=None,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigType, async_add_entities
) -> None:
    """Set up the Met Office weather sensor platform."""
    hass_data = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            MetOfficeCurrentSensor(
                hass_data[METOFFICE_HOURLY_COORDINATOR],
                hass_data,
                True,
                description,
            )
            for description in SENSOR_TYPES
        ]
        + [
            MetOfficeCurrentSensor(
                hass_data[METOFFICE_DAILY_COORDINATOR],
                hass_data,
                False,
                description,
            )
            for description in SENSOR_TYPES
        ],
        False,
    )


class MetOfficeCurrentSensor(CoordinatorEntity, SensorEntity):
    """Implementation of a Met Office current weather condition sensor."""

    def __init__(
        self,
        coordinator,
        hass_data,
        use_3hourly,
        description: SensorEntityDescription,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        mode_label = MODE_3HOURLY_LABEL if use_3hourly else MODE_DAILY_LABEL
        self._attr_device_info = get_device_info(
            coordinates=hass_data[METOFFICE_COORDINATES], name=hass_data[METOFFICE_NAME]
        )
        self._attr_name = f"{hass_data[METOFFICE_NAME]} {description.name} {mode_label}"
        self._attr_unique_id = f"{description.name}_{hass_data[METOFFICE_COORDINATES]}"
        if not use_3hourly:
            self._attr_unique_id = f"{self._attr_unique_id}_{MODE_DAILY}"

        self.use_3hourly = use_3hourly

    @property
    def native_value(self):
        """Return the state of the sensor."""
        value = None

        if self.entity_description.key == "visibility_distance" and hasattr(
            self.coordinator.data.now, "visibility"
        ):
            value = VISIBILITY_DISTANCE_CLASSES.get(
                self.coordinator.data.now.visibility.value
            )

        if self.entity_description.key == "visibility" and hasattr(
            self.coordinator.data.now, "visibility"
        ):
            value = VISIBILITY_CLASSES.get(self.coordinator.data.now.visibility.value)

        elif self.entity_description.key == "weather" and hasattr(
            self.coordinator.data.now, self.entity_description.key
        ):
            value = [
                k
                for k, v in CONDITION_CLASSES.items()
                if self.coordinator.data.now.weather.value in v
            ][0]

        elif hasattr(self.coordinator.data.now, self.entity_description.key):
            value = getattr(self.coordinator.data.now, self.entity_description.key)

            if hasattr(value, "value"):
                value = value.value

        return value

    @property
    def icon(self):
        """Return the icon for the entity card."""
        value = self.entity_description.icon
        if self.entity_description.key == "weather":
            value = self.state
            if value is None:
                value = "sunny"
            elif value == "partlycloudy":
                value = "partly-cloudy"
            value = f"mdi:weather-{value}"

        return value

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_LAST_UPDATE: self.coordinator.data.now.date,
            ATTR_SENSOR_ID: self.entity_description.key,
            ATTR_SITE_ID: self.coordinator.data.site.id,
            ATTR_SITE_NAME: self.coordinator.data.site.name,
        }

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return (
            self.entity_description.entity_registry_enabled_default and self.use_3hourly
        )
