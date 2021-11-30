"""Constants."""
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN

DOMAIN = "broadlink"

DOMAINS_AND_TYPES = {
    REMOTE_DOMAIN: {"RM4MINI", "RM4PRO", "RMMINI", "RMMINIB", "RMPRO"},
    SENSOR_DOMAIN: {
        "A1",
        "RM4MINI",
        "RM4PRO",
        "RMPRO",
        "SP2S",
        "SP3S",
        "SP4",
        "SP4B",
    },
    SWITCH_DOMAIN: {
        "BG1",
        "MP1",
        "RM4MINI",
        "RM4PRO",
        "RMMINI",
        "RMMINIB",
        "RMPRO",
        "SP1",
        "SP2",
        "SP2S",
        "SP3",
        "SP3S",
        "SP4",
        "SP4B",
    },
    LIGHT_DOMAIN: {"LB1"},
}
DEVICE_TYPES = set.union(*DOMAINS_AND_TYPES.values())

DEFAULT_PORT = 80
DEFAULT_TIMEOUT = 5
