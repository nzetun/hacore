"""Support for HomeKit Controller air quality sensors."""
import logging

from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

from homeassistant.components.air_quality import AirQualityEntity
from homeassistant.core import callback

from . import KNOWN_DEVICES, HomeKitEntity

_LOGGER = logging.getLogger(__name__)

AIR_QUALITY_TEXT = {
    0: "unknown",
    1: "excellent",
    2: "good",
    3: "fair",
    4: "inferior",
    5: "poor",
}


class HomeAirQualitySensor(HomeKitEntity, AirQualityEntity):
    """Representation of a HomeKit Controller Air Quality sensor."""

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        _LOGGER.warning(
            "The homekit_controller air_quality entity has been "
            "deprecated and will be removed in 2021.12.0"
        )
        await super().async_added_to_hass()

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Whether or not to enable this entity by default."""
        # This entity is deprecated, so don't enable by default
        return False

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity cares about."""
        return [
            CharacteristicsTypes.AIR_QUALITY,
            CharacteristicsTypes.DENSITY_PM25,
            CharacteristicsTypes.DENSITY_PM10,
            CharacteristicsTypes.DENSITY_OZONE,
            CharacteristicsTypes.DENSITY_NO2,
            CharacteristicsTypes.DENSITY_SO2,
            CharacteristicsTypes.DENSITY_VOC,
        ]

    @property
    def particulate_matter_2_5(self):
        """Return the particulate matter 2.5 level."""
        return self.service.value(CharacteristicsTypes.DENSITY_PM25)

    @property
    def particulate_matter_10(self):
        """Return the particulate matter 10 level."""
        return self.service.value(CharacteristicsTypes.DENSITY_PM10)

    @property
    def ozone(self):
        """Return the O3 (ozone) level."""
        return self.service.value(CharacteristicsTypes.DENSITY_OZONE)

    @property
    def sulphur_dioxide(self):
        """Return the SO2 (sulphur dioxide) level."""
        return self.service.value(CharacteristicsTypes.DENSITY_SO2)

    @property
    def nitrogen_dioxide(self):
        """Return the NO2 (nitrogen dioxide) level."""
        return self.service.value(CharacteristicsTypes.DENSITY_NO2)

    @property
    def air_quality_text(self):
        """Return the Air Quality Index (AQI)."""
        air_quality = self.service.value(CharacteristicsTypes.AIR_QUALITY)
        return AIR_QUALITY_TEXT.get(air_quality, "unknown")

    @property
    def volatile_organic_compounds(self):
        """Return the volatile organic compounds (VOC) level."""
        return self.service.value(CharacteristicsTypes.DENSITY_VOC)

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        data = {"air_quality_text": self.air_quality_text}

        if voc := self.volatile_organic_compounds:
            data["volatile_organic_compounds"] = voc

        return data


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Homekit air quality sensor."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(service):
        if service.short_type != ServicesTypes.AIR_QUALITY_SENSOR:
            return False
        info = {"aid": service.accessory.aid, "iid": service.iid}
        async_add_entities([HomeAirQualitySensor(conn, info)], True)
        return True

    conn.add_listener(async_add_service)
