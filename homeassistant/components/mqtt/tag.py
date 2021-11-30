"""Provides tag scanning for MQTT."""
import functools
import logging

import voluptuous as vol

from homeassistant.const import CONF_DEVICE, CONF_PLATFORM, CONF_VALUE_TEMPLATE
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import EVENT_DEVICE_REGISTRY_UPDATED
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from . import subscription
from .. import mqtt
from .const import (
    ATTR_DISCOVERY_HASH,
    ATTR_DISCOVERY_TOPIC,
    CONF_QOS,
    CONF_TOPIC,
    DOMAIN,
)
from .discovery import MQTT_DISCOVERY_DONE, MQTT_DISCOVERY_UPDATED, clear_discovery_hash
from .mixins import (
    CONF_CONNECTIONS,
    CONF_IDENTIFIERS,
    MQTT_ENTITY_DEVICE_INFO_SCHEMA,
    async_setup_entry_helper,
    cleanup_device_registry,
    device_info_from_config,
)
from .util import valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

TAG = "tag"
TAGS = "mqtt_tags"

PLATFORM_SCHEMA = mqtt.MQTT_BASE_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICE): MQTT_ENTITY_DEVICE_INFO_SCHEMA,
        vol.Optional(CONF_PLATFORM): "mqtt",
        vol.Required(CONF_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    },
    extra=vol.REMOVE_EXTRA,
)


async def async_setup_entry(hass, config_entry):
    """Set up MQTT tag scan dynamically through MQTT discovery."""
    setup = functools.partial(async_setup_tag, hass, config_entry=config_entry)
    await async_setup_entry_helper(hass, "tag", setup, PLATFORM_SCHEMA)


async def async_setup_tag(hass, config, config_entry, discovery_data):
    """Set up the MQTT tag scanner."""
    discovery_hash = discovery_data[ATTR_DISCOVERY_HASH]
    discovery_id = discovery_hash[1]

    device_id = None
    if CONF_DEVICE in config:
        await _update_device(hass, config_entry, config)

        device_registry = await hass.helpers.device_registry.async_get_registry()
        device = device_registry.async_get_device(
            {(DOMAIN, id_) for id_ in config[CONF_DEVICE][CONF_IDENTIFIERS]},
            {tuple(x) for x in config[CONF_DEVICE][CONF_CONNECTIONS]},
        )

        if device is None:
            return
        device_id = device.id

        if TAGS not in hass.data:
            hass.data[TAGS] = {}
        if device_id not in hass.data[TAGS]:
            hass.data[TAGS][device_id] = {}

    tag_scanner = MQTTTagScanner(
        hass,
        config,
        device_id,
        discovery_data,
        config_entry,
    )

    await tag_scanner.setup()

    if device_id:
        hass.data[TAGS][device_id][discovery_id] = tag_scanner


def async_has_tags(hass, device_id):
    """Device has tag scanners."""
    if TAGS not in hass.data or device_id not in hass.data[TAGS]:
        return False
    return hass.data[TAGS][device_id] != {}


class MQTTTagScanner:
    """MQTT Tag scanner."""

    def __init__(self, hass, config, device_id, discovery_data, config_entry):
        """Initialize."""
        self._config = config
        self._config_entry = config_entry
        self.device_id = device_id
        self.discovery_data = discovery_data
        self.hass = hass
        self._remove_discovery = None
        self._remove_device_updated = None
        self._sub_state = None
        self._value_template = None

        self._setup_from_config(config)

    async def discovery_update(self, payload):
        """Handle discovery update."""
        discovery_hash = self.discovery_data[ATTR_DISCOVERY_HASH]
        _LOGGER.info(
            "Got update for tag scanner with hash: %s '%s'", discovery_hash, payload
        )
        if not payload:
            # Empty payload: Remove tag scanner
            _LOGGER.info("Removing tag scanner: %s", discovery_hash)
            await self.tear_down()
            if self.device_id:
                await cleanup_device_registry(self.hass, self.device_id)
        else:
            # Non-empty payload: Update tag scanner
            _LOGGER.info("Updating tag scanner: %s", discovery_hash)
            config = PLATFORM_SCHEMA(payload)
            self._config = config
            if self.device_id:
                await _update_device(self.hass, self._config_entry, config)
            self._setup_from_config(config)
            await self.subscribe_topics()

        async_dispatcher_send(
            self.hass, MQTT_DISCOVERY_DONE.format(discovery_hash), None
        )

    def _setup_from_config(self, config):
        self._value_template = lambda value, error_value: value
        if CONF_VALUE_TEMPLATE in config:
            value_template = config.get(CONF_VALUE_TEMPLATE)
            value_template.hass = self.hass

            self._value_template = value_template.async_render_with_possible_json_value

    async def setup(self):
        """Set up the MQTT tag scanner."""
        discovery_hash = self.discovery_data[ATTR_DISCOVERY_HASH]
        await self.subscribe_topics()
        if self.device_id:
            self._remove_device_updated = self.hass.bus.async_listen(
                EVENT_DEVICE_REGISTRY_UPDATED, self.device_removed
            )
        self._remove_discovery = async_dispatcher_connect(
            self.hass,
            MQTT_DISCOVERY_UPDATED.format(discovery_hash),
            self.discovery_update,
        )
        async_dispatcher_send(
            self.hass, MQTT_DISCOVERY_DONE.format(discovery_hash), None
        )

    async def subscribe_topics(self):
        """Subscribe to MQTT topics."""

        async def tag_scanned(msg):
            tag_id = self._value_template(msg.payload, error_value="").strip()
            if not tag_id:  # No output from template, ignore
                return

            await self.hass.components.tag.async_scan_tag(tag_id, self.device_id)

        self._sub_state = await subscription.async_subscribe_topics(
            self.hass,
            self._sub_state,
            {
                "state_topic": {
                    "topic": self._config[CONF_TOPIC],
                    "msg_callback": tag_scanned,
                    "qos": self._config[CONF_QOS],
                }
            },
        )

    async def device_removed(self, event):
        """Handle the removal of a device."""
        device_id = event.data["device_id"]
        if event.data["action"] != "remove" or device_id != self.device_id:
            return

        await self.tear_down()

    async def tear_down(self):
        """Cleanup tag scanner."""
        discovery_hash = self.discovery_data[ATTR_DISCOVERY_HASH]
        discovery_id = discovery_hash[1]
        discovery_topic = self.discovery_data[ATTR_DISCOVERY_TOPIC]

        clear_discovery_hash(self.hass, discovery_hash)
        if self.device_id:
            self._remove_device_updated()
        self._remove_discovery()

        mqtt.publish(self.hass, discovery_topic, "", retain=True)
        self._sub_state = await subscription.async_unsubscribe_topics(
            self.hass, self._sub_state
        )
        if self.device_id:
            self.hass.data[TAGS][self.device_id].pop(discovery_id)


async def _update_device(hass, config_entry, config):
    """Update device registry."""
    device_registry = await hass.helpers.device_registry.async_get_registry()
    config_entry_id = config_entry.entry_id
    device_info = device_info_from_config(config[CONF_DEVICE])

    if config_entry_id is not None and device_info is not None:
        device_info["config_entry_id"] = config_entry_id
        device_registry.async_get_or_create(**device_info)
