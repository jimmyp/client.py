"""SST authentication tests."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from aiohttp import ClientSession
import orjson
import pytest
from testfixtures import LogCapture

from deebot_client.authentication import Authenticator
from deebot_client.exceptions import ApiTimeoutError
from deebot_client.models import ApiDeviceInfo, Credentials
from deebot_client.sst_authentication import SST_ISSUE_PATH, SstAuthenticator

if TYPE_CHECKING:
    from collections.abc import Sequence

_SST = "SST.eyJhbGciOiJIUzI1NiJ9.payload.signature"


def _session(tokens: Sequence[str] = (_SST,)) -> Mock:
    session = Mock(spec_set=ClientSession)
    session.post = MagicMock()
    responses = []
    for token in tokens:
        response = MagicMock()
        response.raise_for_status = Mock()
        response.read = AsyncMock(
            return_value=orjson.dumps({"code": 0, "data": {"data": {"token": token}}})
        )
        responses.append(response)
    session.post.return_value.__aenter__.side_effect = responses
    return session


def _authenticator() -> Mock:
    authenticator = Mock(spec_set=Authenticator)
    authenticator.authenticate = AsyncMock(
        return_value=Credentials("account_token", "user_id", 9999)
    )
    return authenticator


async def test_SstAuthenticator_issue(ngiot_api_device_info: ApiDeviceInfo) -> None:
    session = _session()
    sst = SstAuthenticator(_authenticator(), session)

    token = await sst.async_get_token(ngiot_api_device_info)

    assert token == _SST
    session.post.assert_called_once()
    args, kwargs = session.post.call_args
    assert args[0] == f"https://api-base.dc-na.ww.ecouser.net{SST_ISSUE_PATH}"
    assert kwargs["headers"]["Authorization"] == "Bearer account_token"
    assert kwargs["json"] == {
        "acl": [
            {
                "policy": [{"obj": ["Endpoint:q287s6:did"], "perms": ["Control"]}],
                "svc": "dim",
            }
        ],
        "exp": 600,
        "sub": "user_id",
    }


async def test_SstAuthenticator_non_ngiot_host(
    ngiot_api_device_info: ApiDeviceInfo,
) -> None:
    ngiot_api_device_info["service"] = {"mqs": "mq-eu.ecouser.net"}
    session = _session()

    await SstAuthenticator(_authenticator(), session).async_get_token(
        ngiot_api_device_info
    )

    assert (
        session.post.call_args.args[0] == f"https://mq-eu.ecouser.net{SST_ISSUE_PATH}"
    )


async def test_SstAuthenticator_cache(ngiot_api_device_info: ApiDeviceInfo) -> None:
    session = _session([_SST, "second"])
    sst = SstAuthenticator(_authenticator(), session)

    first = await sst.async_get_token(ngiot_api_device_info)
    second = await sst.async_get_token(ngiot_api_device_info)

    assert first == second == _SST
    assert session.post.call_count == 1


async def test_SstAuthenticator_cache_per_device(
    ngiot_api_device_info: ApiDeviceInfo,
) -> None:
    other: ApiDeviceInfo = {**ngiot_api_device_info, "did": "other"}
    session = _session([_SST, "second"])
    sst = SstAuthenticator(_authenticator(), session)

    assert await sst.async_get_token(ngiot_api_device_info) == _SST
    assert await sst.async_get_token(other) == "second"
    assert session.post.call_count == 2


async def test_SstAuthenticator_concurrent_requests_mint_once(
    ngiot_api_device_info: ApiDeviceInfo,
) -> None:
    session = _session([_SST, "second"])
    sst = SstAuthenticator(_authenticator(), session)

    tokens = await asyncio.gather(
        sst.async_get_token(ngiot_api_device_info),
        sst.async_get_token(ngiot_api_device_info),
    )

    assert tokens == [_SST, _SST]
    assert session.post.call_count == 1


async def test_SstAuthenticator_invalidate(
    ngiot_api_device_info: ApiDeviceInfo,
) -> None:
    session = _session([_SST, "second"])
    sst = SstAuthenticator(_authenticator(), session)

    await sst.async_get_token(ngiot_api_device_info)
    sst.invalidate("did")

    assert await sst.async_get_token(ngiot_api_device_info) == "second"
    assert session.post.call_count == 2


async def test_SstAuthenticator_expiry(ngiot_api_device_info: ApiDeviceInfo) -> None:
    session = _session([_SST, "second"])
    sst = SstAuthenticator(_authenticator(), session)

    with patch("deebot_client.sst_authentication.time.time", return_value=1000.0):
        await sst.async_get_token(ngiot_api_device_info)
    # 600s * 0.9 = 540s validity; just before the boundary the cache is still used
    with patch("deebot_client.sst_authentication.time.time", return_value=1539.0):
        assert await sst.async_get_token(ngiot_api_device_info) == _SST
    with patch("deebot_client.sst_authentication.time.time", return_value=1541.0):
        assert await sst.async_get_token(ngiot_api_device_info) == "second"


async def test_SstAuthenticator_timeout(ngiot_api_device_info: ApiDeviceInfo) -> None:
    session = _session()
    session.post.return_value.__aenter__.side_effect = TimeoutError()
    sst = SstAuthenticator(_authenticator(), session)

    with pytest.raises(ApiTimeoutError):
        await sst.async_get_token(ngiot_api_device_info)


async def test_SstAuthenticator_does_not_log_tokens(
    ngiot_api_device_info: ApiDeviceInfo,
) -> None:
    sst = SstAuthenticator(_authenticator(), _session())

    with LogCapture() as log:
        await sst.async_get_token(ngiot_api_device_info)

    for record in log.records:
        assert _SST not in record.getMessage()
        assert "account_token" not in record.getMessage()
