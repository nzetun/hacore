"""The tests for the Islamic prayer times sensor platform."""
from unittest.mock import patch

from homeassistant.components import islamic_prayer_times
import homeassistant.util.dt as dt_util

from . import NOW, PRAYER_TIMES, PRAYER_TIMES_TIMESTAMPS

from tests.common import MockConfigEntry


async def test_islamic_prayer_times_sensors(hass, legacy_patchable_time):
    """Test minimum Islamic prayer times configuration."""
    entry = MockConfigEntry(domain=islamic_prayer_times.DOMAIN, data={})
    entry.add_to_hass(hass)

    with patch(
        "prayer_times_calculator.PrayerTimesCalculator.fetch_prayer_times",
        return_value=PRAYER_TIMES,
    ), patch("homeassistant.util.dt.now", return_value=NOW):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        for prayer in PRAYER_TIMES:
            assert (
                hass.states.get(
                    f"sensor.{prayer}_{islamic_prayer_times.const.SENSOR_TYPES[prayer]}"
                ).state
                == PRAYER_TIMES_TIMESTAMPS[prayer].astimezone(dt_util.UTC).isoformat()
            )
