"""SST (short-lived service token) authentication for ngiot devices.

ECOVACS' next-generation IoT transport ("ngiot", used by ``eco-ng`` devices
such as the DEEBOT NEO 2.0 PLUS / ``q287s6``) does not authenticate
``endpoint/control`` calls with the long-lived account token. Instead a
short-lived, narrowly-scoped *service token* (``SST``) is minted per device and
presented as the bearer token for control calls.

Security properties enforced here:

* **Minimal scope** -- the token is requested with ``Control`` permission on the
  single ``Endpoint:<class>:<did>`` only, and a short ``exp`` (10 minutes).
* **Hygiene** -- tokens are cached per-device in memory only, refreshed before
  expiry, can be invalidated on auth failure, and are *never* written to logs.
* **Real TLS** -- minting goes through the shared :class:`aiohttp.ClientSession`,
  which validates the server certificate chain by default. We never disable
  certificate or hostname verification.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import time
from typing import TYPE_CHECKING, Any

from aiohttp import ClientTimeout
import orjson

from .logging_filter import get_logger

if TYPE_CHECKING:
    from aiohttp import ClientSession

    from .authentication import Authenticator
    from .models import ApiDeviceInfo

_LOGGER = get_logger(__name__)

SST_ISSUE_PATH = "/api/new-perm/token/sst/issue"
# Requested validity of the minted token, in seconds (matches the official app).
SST_EXP_SECONDS = 600
# Refresh ahead of expiry so an in-flight control call never carries a token
# that the server has already rejected.
_SST_REFRESH_RATIO = 0.9
_TIMEOUT = ClientTimeout(60)


@dataclass(frozen=True)
class _CachedToken:
    token: str
    expires_at: float


class SstAuthenticator:
    """Mint and cache per-device SST tokens for the ngiot transport."""

    def __init__(self, authenticator: Authenticator, session: ClientSession) -> None:
        self._authenticator = authenticator
        self._session = session
        self._lock = asyncio.Lock()
        self._tokens: dict[str, _CachedToken] = {}

    async def async_get_token(self, device_info: ApiDeviceInfo) -> str:
        """Return a valid SST for the device, minting/refreshing as needed."""
        did = device_info["did"]
        async with self._lock:
            cached = self._tokens.get(did)
            if cached is not None and cached.expires_at > time.time():
                return cached.token

            token = await self._issue(device_info)
            self._tokens[did] = _CachedToken(
                token, time.time() + SST_EXP_SECONDS * _SST_REFRESH_RATIO
            )
            return token

    def invalidate(self, did: str) -> None:
        """Drop any cached token for the device (e.g. after an auth failure)."""
        self._tokens.pop(did, None)

    @staticmethod
    def _sst_issue_base_url(device_info: ApiDeviceInfo) -> str:
        """Derive the api-base host that issues SST tokens for this device.

        SST is minted on the ``api-base`` host, derived from the device's
        ``service.mqs`` host (e.g. ``api-ngiot.dc-na.ww.ecouser.net`` ->
        ``https://api-base.dc-na.ww.ecouser.net``).
        """
        mqs: str = device_info["service"]["mqs"]  # type: ignore[typeddict-item]
        if mqs.startswith("api-ngiot."):
            return "https://api-base." + mqs.split(".", 1)[1]
        return "https://" + mqs

    async def _issue(self, device_info: ApiDeviceInfo) -> str:
        credentials = await self._authenticator.authenticate()
        url = self._sst_issue_base_url(device_info) + SST_ISSUE_PATH
        cls = device_info["class"]
        did = device_info["did"]
        payload: dict[str, Any] = {
            "acl": [
                {
                    "policy": [
                        {"obj": [f"Endpoint:{cls}:{did}"], "perms": ["Control"]}
                    ],
                    "svc": "dim",
                }
            ],
            "exp": SST_EXP_SECONDS,
            "sub": credentials.user_id,
        }
        headers = {
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        _LOGGER.debug("Minting SST for device %s", did)
        async with self._session.post(
            url, json=payload, headers=headers, timeout=_TIMEOUT
        ) as res:
            res.raise_for_status()
            body = orjson.loads(await res.read())
        return str(body["data"]["data"]["token"])
