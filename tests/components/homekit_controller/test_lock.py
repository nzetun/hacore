"""Basic checks for HomeKitLock."""
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

from tests.components.homekit_controller.common import setup_test_component

LOCK_CURRENT_STATE = ("lock-mechanism", "lock-mechanism.current-state")
LOCK_TARGET_STATE = ("lock-mechanism", "lock-mechanism.target-state")


def create_lock_service(accessory):
    """Define a lock characteristics as per page 219 of HAP spec."""
    service = accessory.add_service(ServicesTypes.LOCK_MECHANISM)

    cur_state = service.add_char(CharacteristicsTypes.LOCK_MECHANISM_CURRENT_STATE)
    cur_state.value = 0

    targ_state = service.add_char(CharacteristicsTypes.LOCK_MECHANISM_TARGET_STATE)
    targ_state.value = 0

    # According to the spec, a battery-level characteristic is normally
    # part of a separate service. However as the code was written (which
    # predates this test) the battery level would have to be part of the lock
    # service as it is here.
    targ_state = service.add_char(CharacteristicsTypes.BATTERY_LEVEL)
    targ_state.value = 50

    return service


async def test_switch_change_lock_state(hass, utcnow):
    """Test that we can turn a HomeKit lock on and off again."""
    helper = await setup_test_component(hass, create_lock_service)

    await hass.services.async_call(
        "lock", "lock", {"entity_id": "lock.testdevice"}, blocking=True
    )
    assert helper.characteristics[LOCK_TARGET_STATE].value == 1

    await hass.services.async_call(
        "lock", "unlock", {"entity_id": "lock.testdevice"}, blocking=True
    )
    assert helper.characteristics[LOCK_TARGET_STATE].value == 0


async def test_switch_read_lock_state(hass, utcnow):
    """Test that we can read the state of a HomeKit lock accessory."""
    helper = await setup_test_component(hass, create_lock_service)

    helper.characteristics[LOCK_CURRENT_STATE].value = 0
    helper.characteristics[LOCK_TARGET_STATE].value = 0
    state = await helper.poll_and_get_state()
    assert state.state == "unlocked"
    assert state.attributes["battery_level"] == 50

    helper.characteristics[LOCK_CURRENT_STATE].value = 1
    helper.characteristics[LOCK_TARGET_STATE].value = 1
    state = await helper.poll_and_get_state()
    assert state.state == "locked"

    helper.characteristics[LOCK_CURRENT_STATE].value = 2
    helper.characteristics[LOCK_TARGET_STATE].value = 1
    state = await helper.poll_and_get_state()
    assert state.state == "jammed"

    helper.characteristics[LOCK_CURRENT_STATE].value = 3
    helper.characteristics[LOCK_TARGET_STATE].value = 1
    state = await helper.poll_and_get_state()
    assert state.state == "unknown"

    helper.characteristics[LOCK_CURRENT_STATE].value = 0
    helper.characteristics[LOCK_TARGET_STATE].value = 1
    state = await helper.poll_and_get_state()
    assert state.state == "locking"

    helper.characteristics[LOCK_CURRENT_STATE].value = 1
    helper.characteristics[LOCK_TARGET_STATE].value = 0
    state = await helper.poll_and_get_state()
    assert state.state == "unlocking"
