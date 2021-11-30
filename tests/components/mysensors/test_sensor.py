"""Provide tests for mysensors sensor platform."""
from __future__ import annotations

from typing import Callable

from mysensors.sensor import Sensor
import pytest

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM, UnitSystem

from tests.common import MockConfigEntry


async def test_gps_sensor(
    hass: HomeAssistant,
    gps_sensor: Sensor,
    integration: tuple[MockConfigEntry, Callable[[str], None]],
) -> None:
    """Test a gps sensor."""
    entity_id = "sensor.gps_sensor_1_1"
    _, receive_message = integration

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "40.741894,-73.989311,12"

    altitude = 0
    new_coords = "40.782,-73.965"
    message_string = f"1;1;1;0;49;{new_coords},{altitude}\n"

    receive_message(message_string)
    # the integration adds multiple jobs to do the update currently
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == f"{new_coords},{altitude}"


async def test_power_sensor(
    hass: HomeAssistant,
    power_sensor: Sensor,
    integration: tuple[MockConfigEntry, Callable[[str], None]],
) -> None:
    """Test a power sensor."""
    entity_id = "sensor.power_sensor_1_1"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "1200"
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_POWER
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == POWER_WATT
    assert state.attributes[ATTR_STATE_CLASS] == STATE_CLASS_MEASUREMENT


async def test_energy_sensor(
    hass: HomeAssistant,
    energy_sensor: Sensor,
    integration: tuple[MockConfigEntry, Callable[[str], None]],
) -> None:
    """Test an energy sensor."""
    entity_id = "sensor.energy_sensor_1_1"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "18000"
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_ENERGY
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == ENERGY_KILO_WATT_HOUR
    assert state.attributes[ATTR_STATE_CLASS] == STATE_CLASS_TOTAL_INCREASING


async def test_sound_sensor(
    hass: HomeAssistant,
    sound_sensor: Sensor,
    integration: tuple[MockConfigEntry, Callable[[str], None]],
) -> None:
    """Test a sound sensor."""
    entity_id = "sensor.sound_sensor_1_1"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "10"
    assert state.attributes[ATTR_ICON] == "mdi:volume-high"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "dB"


async def test_distance_sensor(
    hass: HomeAssistant,
    distance_sensor: Sensor,
    integration: tuple[MockConfigEntry, Callable[[str], None]],
) -> None:
    """Test a distance sensor."""
    entity_id = "sensor.distance_sensor_1_1"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "15"
    assert state.attributes[ATTR_ICON] == "mdi:ruler"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "cm"


@pytest.mark.parametrize(
    "unit_system, unit",
    [(METRIC_SYSTEM, TEMP_CELSIUS), (IMPERIAL_SYSTEM, TEMP_FAHRENHEIT)],
)
async def test_temperature_sensor(
    hass: HomeAssistant,
    temperature_sensor: Sensor,
    integration: tuple[MockConfigEntry, Callable[[str], None]],
    unit_system: UnitSystem,
    unit: str,
) -> None:
    """Test a temperature sensor."""
    entity_id = "sensor.temperature_sensor_1_1"
    hass.config.units = unit_system
    _, receive_message = integration
    temperature = "22.0"
    message_string = f"1;1;1;0;0;{temperature}\n"

    receive_message(message_string)
    # the integration adds multiple jobs to do the update currently
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == temperature
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_TEMPERATURE
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == unit
    assert state.attributes[ATTR_STATE_CLASS] == STATE_CLASS_MEASUREMENT
