"""Helpers to setup multi-factor auth module."""
import logging

import voluptuous as vol
import voluptuous_serialize

from homeassistant import data_entry_flow
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

WS_TYPE_SETUP_MFA = "auth/setup_mfa"
SCHEMA_WS_SETUP_MFA = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_SETUP_MFA,
        vol.Exclusive("mfa_module_id", "module_or_flow_id"): str,
        vol.Exclusive("flow_id", "module_or_flow_id"): str,
        vol.Optional("user_input"): object,
    }
)

WS_TYPE_DEPOSE_MFA = "auth/depose_mfa"
SCHEMA_WS_DEPOSE_MFA = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {vol.Required("type"): WS_TYPE_DEPOSE_MFA, vol.Required("mfa_module_id"): str}
)

DATA_SETUP_FLOW_MGR = "auth_mfa_setup_flow_manager"

_LOGGER = logging.getLogger(__name__)


class MfaFlowManager(data_entry_flow.FlowManager):
    """Manage multi factor authentication flows."""

    async def async_create_flow(self, handler_key, *, context, data):
        """Create a setup flow. handler is a mfa module."""
        mfa_module = self.hass.auth.get_auth_mfa_module(handler_key)
        if mfa_module is None:
            raise ValueError(f"Mfa module {handler_key} is not found")

        user_id = data.pop("user_id")
        return await mfa_module.async_setup_flow(user_id)

    async def async_finish_flow(self, flow, result):
        """Complete an mfs setup flow."""
        _LOGGER.debug("flow_result: %s", result)
        return result


async def async_setup(hass):
    """Init mfa setup flow manager."""
    hass.data[DATA_SETUP_FLOW_MGR] = MfaFlowManager(hass)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_SETUP_MFA, websocket_setup_mfa, SCHEMA_WS_SETUP_MFA
    )

    hass.components.websocket_api.async_register_command(
        WS_TYPE_DEPOSE_MFA, websocket_depose_mfa, SCHEMA_WS_DEPOSE_MFA
    )


@callback
@websocket_api.ws_require_user(allow_system_user=False)
def websocket_setup_mfa(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg
):
    """Return a setup flow for mfa auth module."""

    async def async_setup_flow(msg):
        """Return a setup flow for mfa auth module."""
        flow_manager = hass.data[DATA_SETUP_FLOW_MGR]

        if (flow_id := msg.get("flow_id")) is not None:
            result = await flow_manager.async_configure(flow_id, msg.get("user_input"))
            connection.send_message(
                websocket_api.result_message(msg["id"], _prepare_result_json(result))
            )
            return

        mfa_module_id = msg.get("mfa_module_id")
        mfa_module = hass.auth.get_auth_mfa_module(mfa_module_id)
        if mfa_module is None:
            connection.send_message(
                websocket_api.error_message(
                    msg["id"], "no_module", f"MFA module {mfa_module_id} is not found"
                )
            )
            return

        result = await flow_manager.async_init(
            mfa_module_id, data={"user_id": connection.user.id}
        )

        connection.send_message(
            websocket_api.result_message(msg["id"], _prepare_result_json(result))
        )

    hass.async_create_task(async_setup_flow(msg))


@callback
@websocket_api.ws_require_user(allow_system_user=False)
def websocket_depose_mfa(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg
):
    """Remove user from mfa module."""

    async def async_depose(msg):
        """Remove user from mfa auth module."""
        mfa_module_id = msg["mfa_module_id"]
        try:
            await hass.auth.async_disable_user_mfa(
                connection.user, msg["mfa_module_id"]
            )
        except ValueError as err:
            connection.send_message(
                websocket_api.error_message(
                    msg["id"],
                    "disable_failed",
                    f"Cannot disable MFA Module {mfa_module_id}: {err}",
                )
            )
            return

        connection.send_message(websocket_api.result_message(msg["id"], "done"))

    hass.async_create_task(async_depose(msg))


def _prepare_result_json(result):
    """Convert result to JSON."""
    if result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY:
        data = result.copy()
        return data

    if result["type"] != data_entry_flow.RESULT_TYPE_FORM:
        return result

    data = result.copy()

    if (schema := data["data_schema"]) is None:
        data["data_schema"] = []
    else:
        data["data_schema"] = voluptuous_serialize.convert(schema)

    return data
