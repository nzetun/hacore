"""Common utils for Litter-Robot tests."""
from datetime import datetime

from homeassistant.components.litterrobot import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

BASE_PATH = "homeassistant.components.litterrobot"
CONFIG = {DOMAIN: {CONF_USERNAME: "user@example.com", CONF_PASSWORD: "password"}}

ROBOT_NAME = "Test"
ROBOT_SERIAL = "LR3C012345"
ROBOT_DATA = {
    "powerStatus": "AC",
    "lastSeen": datetime.now().isoformat(),
    "cleanCycleWaitTimeMinutes": "7",
    "unitStatus": "RDY",
    "litterRobotNickname": ROBOT_NAME,
    "cycleCount": "15",
    "panelLockActive": "0",
    "cyclesAfterDrawerFull": "0",
    "litterRobotSerial": ROBOT_SERIAL,
    "cycleCapacity": "30",
    "litterRobotId": "a0123b4567cd8e",
    "nightLightActive": "1",
    "sleepModeActive": "112:50:19",
}

VACUUM_ENTITY_ID = "vacuum.test_litter_box"
