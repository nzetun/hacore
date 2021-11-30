"""The tests for sensor recorder platform."""
# pylint: disable=protected-access,invalid-name
from datetime import timedelta
import threading
from unittest.mock import patch

import pytest
from pytest import approx

from homeassistant.components import recorder
from homeassistant.components.recorder.const import DATA_INSTANCE
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util
from homeassistant.util.unit_system import METRIC_SYSTEM

from .common import (
    async_wait_recording_done_without_instance,
    create_engine_test,
    trigger_db_commit,
)

from tests.common import (
    async_fire_time_changed,
    async_init_recorder_component,
    init_recorder_component,
)

POWER_SENSOR_ATTRIBUTES = {
    "device_class": "power",
    "state_class": "measurement",
    "unit_of_measurement": "kW",
}
TEMPERATURE_SENSOR_ATTRIBUTES = {
    "device_class": "temperature",
    "state_class": "measurement",
    "unit_of_measurement": "°C",
}


async def test_validate_statistics(hass, hass_ws_client):
    """Test validate_statistics can be called."""
    id = 1

    def next_id():
        nonlocal id
        id += 1
        return id

    async def assert_validation_result(client, expected_result):
        await client.send_json(
            {"id": next_id(), "type": "recorder/validate_statistics"}
        )
        response = await client.receive_json()
        assert response["success"]
        assert response["result"] == expected_result

    # No statistics, no state - empty response
    await hass.async_add_executor_job(init_recorder_component, hass)
    client = await hass_ws_client()
    await assert_validation_result(client, {})


async def test_clear_statistics(hass, hass_ws_client):
    """Test removing statistics."""
    now = dt_util.utcnow()

    units = METRIC_SYSTEM
    attributes = POWER_SENSOR_ATTRIBUTES
    state = 10
    value = 10000

    hass.config.units = units
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "history", {})
    await async_setup_component(hass, "sensor", {})
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)
    hass.states.async_set("sensor.test1", state, attributes=attributes)
    hass.states.async_set("sensor.test2", state * 2, attributes=attributes)
    hass.states.async_set("sensor.test3", state * 3, attributes=attributes)
    await hass.async_block_till_done()

    await hass.async_add_executor_job(trigger_db_commit, hass)
    await hass.async_block_till_done()

    hass.data[DATA_INSTANCE].do_adhoc_statistics(start=now)
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "history/statistics_during_period",
            "start_time": now.isoformat(),
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    expected_response = {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": now.isoformat(),
                "end": (now + timedelta(minutes=5)).isoformat(),
                "mean": approx(value),
                "min": approx(value),
                "max": approx(value),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ],
        "sensor.test2": [
            {
                "statistic_id": "sensor.test2",
                "start": now.isoformat(),
                "end": (now + timedelta(minutes=5)).isoformat(),
                "mean": approx(value * 2),
                "min": approx(value * 2),
                "max": approx(value * 2),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ],
        "sensor.test3": [
            {
                "statistic_id": "sensor.test3",
                "start": now.isoformat(),
                "end": (now + timedelta(minutes=5)).isoformat(),
                "mean": approx(value * 3),
                "min": approx(value * 3),
                "max": approx(value * 3),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ],
    }
    assert response["result"] == expected_response

    await client.send_json(
        {
            "id": 2,
            "type": "recorder/clear_statistics",
            "statistic_ids": ["sensor.test"],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 3,
            "type": "history/statistics_during_period",
            "start_time": now.isoformat(),
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == expected_response

    await client.send_json(
        {
            "id": 4,
            "type": "recorder/clear_statistics",
            "statistic_ids": ["sensor.test1", "sensor.test3"],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 5,
            "type": "history/statistics_during_period",
            "start_time": now.isoformat(),
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"sensor.test2": expected_response["sensor.test2"]}


@pytest.mark.parametrize("new_unit", ["dogs", None])
async def test_update_statistics_metadata(hass, hass_ws_client, new_unit):
    """Test removing statistics."""
    now = dt_util.utcnow()

    units = METRIC_SYSTEM
    attributes = POWER_SENSOR_ATTRIBUTES
    state = 10

    hass.config.units = units
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "history", {})
    await async_setup_component(hass, "sensor", {})
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)
    hass.states.async_set("sensor.test", state, attributes=attributes)
    await hass.async_block_till_done()

    await hass.async_add_executor_job(trigger_db_commit, hass)
    await hass.async_block_till_done()

    hass.data[DATA_INSTANCE].do_adhoc_statistics(period="hourly", start=now)
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)

    client = await hass_ws_client()

    await client.send_json({"id": 1, "type": "history/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "name": None,
            "source": "recorder",
            "unit_of_measurement": "W",
        }
    ]

    await client.send_json(
        {
            "id": 2,
            "type": "recorder/update_statistics_metadata",
            "statistic_id": "sensor.test",
            "unit_of_measurement": new_unit,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)

    await client.send_json({"id": 3, "type": "history/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "name": None,
            "source": "recorder",
            "unit_of_measurement": new_unit,
        }
    ]


async def test_recorder_info(hass, hass_ws_client):
    """Test getting recorder status."""
    client = await hass_ws_client()
    await async_init_recorder_component(hass)

    # Ensure there are no queued events
    await async_wait_recording_done_without_instance(hass)

    await client.send_json({"id": 1, "type": "recorder/info"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "backlog": 0,
        "max_backlog": 30000,
        "migration_in_progress": False,
        "recording": True,
        "thread_running": True,
    }


async def test_recorder_info_no_recorder(hass, hass_ws_client):
    """Test getting recorder status when recorder is not present."""
    client = await hass_ws_client()

    await client.send_json({"id": 1, "type": "recorder/info"})
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "unknown_command"


async def test_recorder_info_bad_recorder_config(hass, hass_ws_client):
    """Test getting recorder status when recorder is not started."""
    config = {recorder.CONF_DB_URL: "sqlite://no_file", recorder.CONF_DB_RETRY_WAIT: 0}

    client = await hass_ws_client()

    with patch("homeassistant.components.recorder.migration.migrate_schema"):
        assert not await async_setup_component(
            hass, recorder.DOMAIN, {recorder.DOMAIN: config}
        )
        assert recorder.DOMAIN not in hass.config.components
    await hass.async_block_till_done()

    # Wait for recorder to shut down
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].join)

    await client.send_json({"id": 1, "type": "recorder/info"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["recording"] is False
    assert response["result"]["thread_running"] is False


async def test_recorder_info_migration_queue_exhausted(hass, hass_ws_client):
    """Test getting recorder status when recorder queue is exhausted."""
    assert recorder.util.async_migration_in_progress(hass) is False

    migration_done = threading.Event()

    real_migration = recorder.migration.migrate_schema

    def stalled_migration(*args):
        """Make migration stall."""
        nonlocal migration_done
        migration_done.wait()
        return real_migration(*args)

    with patch(
        "homeassistant.components.recorder.Recorder.async_periodic_statistics"
    ), patch(
        "homeassistant.components.recorder.create_engine", new=create_engine_test
    ), patch.object(
        recorder, "MAX_QUEUE_BACKLOG", 1
    ), patch(
        "homeassistant.components.recorder.migration.migrate_schema",
        wraps=stalled_migration,
    ):
        await async_setup_component(
            hass, "recorder", {"recorder": {"db_url": "sqlite://"}}
        )
        hass.states.async_set("my.entity", "on", {})
        await hass.async_block_till_done()

        # Detect queue full
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=2))
        await hass.async_block_till_done()

        client = await hass_ws_client()

        # Check the status
        await client.send_json({"id": 1, "type": "recorder/info"})
        response = await client.receive_json()
        assert response["success"]
        assert response["result"]["migration_in_progress"] is True
        assert response["result"]["recording"] is False
        assert response["result"]["thread_running"] is True

    # Let migration finish
    migration_done.set()
    await async_wait_recording_done_without_instance(hass)

    # Check the status after migration finished
    await client.send_json({"id": 2, "type": "recorder/info"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["migration_in_progress"] is False
    assert response["result"]["recording"] is True
    assert response["result"]["thread_running"] is True
