"""Support for MQTT sensors."""
from __future__ import annotations

from datetime import timedelta
import functools
import logging

import voluptuous as vol

from homeassistant.components import sensor
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DEVICE_CLASSES_SCHEMA,
    ENTITY_ID_FORMAT,
    STATE_CLASSES_SCHEMA,
    SensorEntity,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_FORCE_UPDATE,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
    DEVICE_CLASS_DATE,
    DEVICE_CLASS_TIMESTAMP,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from . import PLATFORMS, subscription
from .. import mqtt
from .const import CONF_QOS, CONF_STATE_TOPIC, DOMAIN
from .debug_info import log_messages
from .mixins import (
    MQTT_ENTITY_COMMON_SCHEMA,
    MqttAvailability,
    MqttEntity,
    async_setup_entry_helper,
)

_LOGGER = logging.getLogger(__name__)

CONF_EXPIRE_AFTER = "expire_after"
CONF_LAST_RESET_TOPIC = "last_reset_topic"
CONF_LAST_RESET_VALUE_TEMPLATE = "last_reset_value_template"

MQTT_SENSOR_ATTRIBUTES_BLOCKED = frozenset(
    {
        sensor.ATTR_LAST_RESET,
        sensor.ATTR_STATE_CLASS,
    }
)

DEFAULT_NAME = "MQTT Sensor"
DEFAULT_FORCE_UPDATE = False


def validate_options(conf):
    """Validate options.

    If last reset topic is present it must be same as the state topic.
    """
    if (
        CONF_LAST_RESET_TOPIC in conf
        and CONF_STATE_TOPIC in conf
        and conf[CONF_LAST_RESET_TOPIC] != conf[CONF_STATE_TOPIC]
    ):
        _LOGGER.warning(
            "'%s' must be same as '%s'", CONF_LAST_RESET_TOPIC, CONF_STATE_TOPIC
        )

    if CONF_LAST_RESET_TOPIC in conf and CONF_LAST_RESET_VALUE_TEMPLATE not in conf:
        _LOGGER.warning(
            "'%s' must be set if '%s' is set",
            CONF_LAST_RESET_VALUE_TEMPLATE,
            CONF_LAST_RESET_TOPIC,
        )

    return conf


_PLATFORM_SCHEMA_BASE = mqtt.MQTT_RO_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_EXPIRE_AFTER): cv.positive_int,
        vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
        vol.Optional(CONF_LAST_RESET_TOPIC): mqtt.valid_subscribe_topic,
        vol.Optional(CONF_LAST_RESET_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_STATE_CLASS): STATE_CLASSES_SCHEMA,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

PLATFORM_SCHEMA = vol.All(
    cv.deprecated(CONF_LAST_RESET_TOPIC),
    _PLATFORM_SCHEMA_BASE,
    validate_options,
)

DISCOVERY_SCHEMA = vol.All(
    cv.deprecated(CONF_LAST_RESET_TOPIC),
    _PLATFORM_SCHEMA_BASE.extend({}, extra=vol.REMOVE_EXTRA),
    validate_options,
)


async def async_setup_platform(
    hass: HomeAssistant, config: ConfigType, async_add_entities, discovery_info=None
):
    """Set up MQTT sensors through configuration.yaml."""
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    await _async_setup_entity(hass, async_add_entities, config)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT sensors dynamically through MQTT discovery."""
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, sensor.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass, async_add_entities, config: ConfigType, config_entry=None, discovery_data=None
):
    """Set up MQTT sensor."""
    async_add_entities([MqttSensor(hass, config, config_entry, discovery_data)])


class MqttSensor(MqttEntity, SensorEntity):
    """Representation of a sensor that can be updated using MQTT."""

    _entity_id_format = ENTITY_ID_FORMAT
    _attr_last_reset = None
    _attributes_extra_blocked = MQTT_SENSOR_ATTRIBUTES_BLOCKED

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize the sensor."""
        self._state = None
        self._expiration_trigger = None

        expire_after = config.get(CONF_EXPIRE_AFTER)
        if expire_after is not None and expire_after > 0:
            self._expired = True
        else:
            self._expired = None

        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema():
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config):
        """(Re)Setup the entity."""
        template = self._config.get(CONF_VALUE_TEMPLATE)
        if template is not None:
            template.hass = self.hass
        last_reset_template = self._config.get(CONF_LAST_RESET_VALUE_TEMPLATE)
        if last_reset_template is not None:
            last_reset_template.hass = self.hass

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""
        topics = {}

        def _update_state(msg):
            payload = msg.payload
            # auto-expire enabled?
            expire_after = self._config.get(CONF_EXPIRE_AFTER)
            if expire_after is not None and expire_after > 0:
                # When expire_after is set, and we receive a message, assume device is not expired since it has to be to receive the message
                self._expired = False

                # Reset old trigger
                if self._expiration_trigger:
                    self._expiration_trigger()
                    self._expiration_trigger = None

                # Set new trigger
                expiration_at = dt_util.utcnow() + timedelta(seconds=expire_after)

                self._expiration_trigger = async_track_point_in_utc_time(
                    self.hass, self._value_is_expired, expiration_at
                )

            template = self._config.get(CONF_VALUE_TEMPLATE)
            if template is not None:
                variables = {"entity_id": self.entity_id}
                payload = template.async_render_with_possible_json_value(
                    payload,
                    self._state,
                    variables=variables,
                )

            if payload is not None and self.device_class in (
                DEVICE_CLASS_DATE,
                DEVICE_CLASS_TIMESTAMP,
            ):
                if (payload := dt_util.parse_datetime(payload)) is None:
                    _LOGGER.warning(
                        "Invalid state message '%s' from '%s'", msg.payload, msg.topic
                    )
                elif self.device_class == DEVICE_CLASS_DATE:
                    payload = payload.date()

            self._state = payload

        def _update_last_reset(msg):
            payload = msg.payload

            template = self._config.get(CONF_LAST_RESET_VALUE_TEMPLATE)
            if template is not None:
                variables = {"entity_id": self.entity_id}
                payload = template.async_render_with_possible_json_value(
                    payload,
                    self._state,
                    variables=variables,
                )
            if not payload:
                _LOGGER.debug("Ignoring empty last_reset message from '%s'", msg.topic)
                return
            try:
                last_reset = dt_util.parse_datetime(payload)
                if last_reset is None:
                    raise ValueError
                self._attr_last_reset = last_reset
            except ValueError:
                _LOGGER.warning(
                    "Invalid last_reset message '%s' from '%s'", msg.payload, msg.topic
                )

        @callback
        @log_messages(self.hass, self.entity_id)
        def message_received(msg):
            """Handle new MQTT messages."""
            _update_state(msg)
            if CONF_LAST_RESET_VALUE_TEMPLATE in self._config and (
                CONF_LAST_RESET_TOPIC not in self._config
                or self._config[CONF_LAST_RESET_TOPIC] == self._config[CONF_STATE_TOPIC]
            ):
                _update_last_reset(msg)
            self.async_write_ha_state()

        topics["state_topic"] = {
            "topic": self._config[CONF_STATE_TOPIC],
            "msg_callback": message_received,
            "qos": self._config[CONF_QOS],
        }

        @callback
        @log_messages(self.hass, self.entity_id)
        def last_reset_message_received(msg):
            """Handle new last_reset messages."""
            _update_last_reset(msg)
            self.async_write_ha_state()

        if (
            CONF_LAST_RESET_TOPIC in self._config
            and self._config[CONF_LAST_RESET_TOPIC] != self._config[CONF_STATE_TOPIC]
        ):
            topics["last_reset_topic"] = {
                "topic": self._config[CONF_LAST_RESET_TOPIC],
                "msg_callback": last_reset_message_received,
                "qos": self._config[CONF_QOS],
            }

        self._sub_state = await subscription.async_subscribe_topics(
            self.hass, self._sub_state, topics
        )

    @callback
    def _value_is_expired(self, *_):
        """Triggered when value is expired."""
        self._expiration_trigger = None
        self._expired = True
        self.async_write_ha_state()

    @property
    def native_unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._config.get(CONF_UNIT_OF_MEASUREMENT)

    @property
    def force_update(self):
        """Force update."""
        return self._config[CONF_FORCE_UPDATE]

    @property
    def native_value(self):
        """Return the state of the entity."""
        return self._state

    @property
    def device_class(self) -> str | None:
        """Return the device class of the sensor."""
        return self._config.get(CONF_DEVICE_CLASS)

    @property
    def state_class(self) -> str | None:
        """Return the state class of the sensor."""
        return self._config.get(CONF_STATE_CLASS)

    @property
    def available(self) -> bool:
        """Return true if the device is available and value has not expired."""
        expire_after = self._config.get(CONF_EXPIRE_AFTER)
        # mypy doesn't know about fget: https://github.com/python/mypy/issues/6185
        return MqttAvailability.available.fget(self) and (  # type: ignore[attr-defined]
            expire_after is None or not self._expired
        )
