"""Support for hunterdouglass_powerview sensors."""
from aiopvapi.resources.shade import factory as PvShade

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    ENTITY_CATEGORY_DIAGNOSTIC,
    PERCENTAGE,
)
from homeassistant.core import callback

from .const import (
    COORDINATOR,
    DEVICE_INFO,
    DOMAIN,
    PV_API,
    PV_ROOM_DATA,
    PV_SHADE_DATA,
    ROOM_ID_IN_SHADE,
    ROOM_NAME_UNICODE,
    SHADE_BATTERY_LEVEL,
    SHADE_BATTERY_LEVEL_MAX,
)
from .entity import ShadeEntity


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the hunter douglas shades sensors."""

    pv_data = hass.data[DOMAIN][entry.entry_id]
    room_data = pv_data[PV_ROOM_DATA]
    shade_data = pv_data[PV_SHADE_DATA]
    pv_request = pv_data[PV_API]
    coordinator = pv_data[COORDINATOR]
    device_info = pv_data[DEVICE_INFO]

    entities = []
    for raw_shade in shade_data.values():
        shade = PvShade(raw_shade, pv_request)
        if SHADE_BATTERY_LEVEL not in shade.raw_data:
            continue
        name_before_refresh = shade.name
        room_id = shade.raw_data.get(ROOM_ID_IN_SHADE)
        room_name = room_data.get(room_id, {}).get(ROOM_NAME_UNICODE, "")
        entities.append(
            PowerViewShadeBatterySensor(
                coordinator, device_info, room_name, shade, name_before_refresh
            )
        )
    async_add_entities(entities)


class PowerViewShadeBatterySensor(ShadeEntity, SensorEntity):
    """Representation of an shade battery charge sensor."""

    _attr_entity_category = ENTITY_CATEGORY_DIAGNOSTIC

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return PERCENTAGE

    @property
    def name(self):
        """Name of the shade battery."""
        return f"{self._shade_name} Battery"

    @property
    def device_class(self):
        """Shade battery Class."""
        return DEVICE_CLASS_BATTERY

    @property
    def unique_id(self):
        """Shade battery Uniqueid."""
        return f"{self._unique_id}_charge"

    @property
    def native_value(self):
        """Get the current value in percentage."""
        return round(
            self._shade.raw_data[SHADE_BATTERY_LEVEL] / SHADE_BATTERY_LEVEL_MAX * 100
        )

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._async_update_shade_from_group)
        )

    @callback
    def _async_update_shade_from_group(self):
        """Update with new data from the coordinator."""
        self._shade.raw_data = self.coordinator.data[self._shade.id]
        self.async_write_ha_state()
