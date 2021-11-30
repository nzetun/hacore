"""Constants for the devolo Home Network integration."""

from datetime import timedelta

DOMAIN = "devolo_home_network"
PLATFORMS = ["sensor"]

PRODUCT = "product"
SERIAL_NUMBER = "serial_number"
TITLE = "title"

LONG_UPDATE_INTERVAL = timedelta(minutes=5)
SHORT_UPDATE_INTERVAL = timedelta(seconds=15)

CONNECTED_PLC_DEVICES = "connected_plc_devices"
CONNECTED_WIFI_CLIENTS = "connected_wifi_clients"
NEIGHBORING_WIFI_NETWORKS = "neighboring_wifi_networks"
