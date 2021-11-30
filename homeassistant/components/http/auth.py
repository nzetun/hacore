"""Authentication for HTTP component."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
from ipaddress import ip_address
import logging
import secrets
from typing import Final
from urllib.parse import unquote

from aiohttp import hdrs
from aiohttp.web import Application, Request, StreamResponse, middleware
import jwt

from homeassistant.auth.models import User
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util
from homeassistant.util.network import is_local

from .const import KEY_AUTHENTICATED, KEY_HASS_REFRESH_TOKEN_ID, KEY_HASS_USER
from .request_context import current_request

_LOGGER = logging.getLogger(__name__)

DATA_API_PASSWORD: Final = "api_password"
DATA_SIGN_SECRET: Final = "http.auth.sign_secret"
SIGN_QUERY_PARAM: Final = "authSig"


@callback
def async_sign_path(
    hass: HomeAssistant, refresh_token_id: str, path: str, expiration: timedelta
) -> str:
    """Sign a path for temporary access without auth header."""
    if (secret := hass.data.get(DATA_SIGN_SECRET)) is None:
        secret = hass.data[DATA_SIGN_SECRET] = secrets.token_hex()

    now = dt_util.utcnow()
    encoded = jwt.encode(
        {
            "iss": refresh_token_id,
            "path": unquote(path),
            "iat": now,
            "exp": now + expiration,
        },
        secret,
        algorithm="HS256",
    )
    return f"{path}?{SIGN_QUERY_PARAM}={encoded}"


@callback
def async_user_not_allowed_do_auth(
    hass: HomeAssistant, user: User, request: Request | None = None
) -> str | None:
    """Validate that user is not allowed to do auth things."""
    if not user.is_active:
        return "User is not active"

    if not user.local_only:
        return None

    # User is marked as local only, check if they are allowed to do auth
    if request is None:
        request = current_request.get()

    if not request:
        return "No request available to validate local access"

    if "cloud" in hass.config.components:
        # pylint: disable=import-outside-toplevel
        from hass_nabucasa import remote

        if remote.is_cloud_request.get():
            return "User is local only"

    try:
        remote = ip_address(request.remote)
    except ValueError:
        return "Invalid remote IP"

    if is_local(remote):
        return None

    return "User cannot authenticate remotely"


@callback
def setup_auth(hass: HomeAssistant, app: Application) -> None:
    """Create auth middleware for the app."""

    async def async_validate_auth_header(request: Request) -> bool:
        """
        Test authorization header against access token.

        Basic auth_type is legacy code, should be removed with api_password.
        """
        try:
            auth_type, auth_val = request.headers.get(hdrs.AUTHORIZATION, "").split(
                " ", 1
            )
        except ValueError:
            # If no space in authorization header
            return False

        if auth_type != "Bearer":
            return False

        refresh_token = await hass.auth.async_validate_access_token(auth_val)

        if refresh_token is None:
            return False

        if async_user_not_allowed_do_auth(hass, refresh_token.user, request):
            return False

        request[KEY_HASS_USER] = refresh_token.user
        request[KEY_HASS_REFRESH_TOKEN_ID] = refresh_token.id
        return True

    async def async_validate_signed_request(request: Request) -> bool:
        """Validate a signed request."""
        if (secret := hass.data.get(DATA_SIGN_SECRET)) is None:
            return False

        if (signature := request.query.get(SIGN_QUERY_PARAM)) is None:
            return False

        try:
            claims = jwt.decode(
                signature, secret, algorithms=["HS256"], options={"verify_iss": False}
            )
        except jwt.InvalidTokenError:
            return False

        if claims["path"] != request.path:
            return False

        refresh_token = await hass.auth.async_get_refresh_token(claims["iss"])

        if refresh_token is None:
            return False

        request[KEY_HASS_USER] = refresh_token.user
        request[KEY_HASS_REFRESH_TOKEN_ID] = refresh_token.id
        return True

    @middleware
    async def auth_middleware(
        request: Request, handler: Callable[[Request], Awaitable[StreamResponse]]
    ) -> StreamResponse:
        """Authenticate as middleware."""
        authenticated = False

        if hdrs.AUTHORIZATION in request.headers and await async_validate_auth_header(
            request
        ):
            authenticated = True
            auth_type = "bearer token"

        # We first start with a string check to avoid parsing query params
        # for every request.
        elif (
            request.method == "GET"
            and SIGN_QUERY_PARAM in request.query
            and await async_validate_signed_request(request)
        ):
            authenticated = True
            auth_type = "signed request"

        if authenticated:
            _LOGGER.debug(
                "Authenticated %s for %s using %s",
                request.remote,
                request.path,
                auth_type,
            )

        request[KEY_AUTHENTICATED] = authenticated
        return await handler(request)

    app.middlewares.append(auth_middleware)
