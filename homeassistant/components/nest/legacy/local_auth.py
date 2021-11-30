"""Local Nest authentication for the legacy api."""
import asyncio
from functools import partial
from http import HTTPStatus

from nest.nest import AUTHORIZE_URL, AuthorizationError, NestAuth

from homeassistant.core import callback

from ..config_flow import CodeInvalid, NestAuthError, register_flow_implementation
from .const import DOMAIN


@callback
def initialize(hass, client_id, client_secret):
    """Initialize a local auth provider."""
    register_flow_implementation(
        hass,
        DOMAIN,
        "configuration.yaml",
        partial(generate_auth_url, client_id),
        partial(resolve_auth_code, hass, client_id, client_secret),
    )


async def generate_auth_url(client_id, flow_id):
    """Generate an authorize url."""
    return AUTHORIZE_URL.format(client_id, flow_id)


async def resolve_auth_code(hass, client_id, client_secret, code):
    """Resolve an authorization code."""

    result = asyncio.Future()
    auth = NestAuth(
        client_id=client_id,
        client_secret=client_secret,
        auth_callback=result.set_result,
    )
    auth.pin = code

    try:
        await hass.async_add_executor_job(auth.login)
        return await result
    except AuthorizationError as err:
        if err.response.status_code == HTTPStatus.UNAUTHORIZED:
            raise CodeInvalid() from err
        raise NestAuthError(
            f"Unknown error: {err} ({err.response.status_code})"
        ) from err
