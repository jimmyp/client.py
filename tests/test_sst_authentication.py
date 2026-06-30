"""ngiot SST authentication tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import orjson
import pytest
from testfixtures import LogCapture

from deebot_client.authentication import Authenticator
from deebot_client.models import ApiDeviceInfo, Credentials
from deebot_client.sst_authentication import SST_ISSUE_PATH, SstAuthenticator
from tests.ngiot_fakes import FakeResponse, FakeSession

_ACCOUNT_TOKEN = "ACCOUNT_TOKEN_SECRET"  # noqa: S105
_SST = "SST.eyJhbGciOiJIUzI1NiJ9.payload.signature"
_DID = "did-abc-123"


def _device_info() -> ApiDeviceInfo:
    info: dict[str, Any] = {
        "class": "q287s6",
        "did": _DID,
        "name": "name",
        "resource": "res9",
        "company": "eco-ng",
        "service": {"mqs": "api-ngiot.dc-na.ww.ecouser.net"},
    }
    return info  # type: ignore[return-value]


def _issue_response(token: str = _SST) -> FakeResponse:
    return FakeResponse(orjson.dumps({"code": 0, "data": {"data": {"token": token}}}))


def _authenticator() -> Authenticator:
    auth = Mock(spec_set=Authenticator)
    auth.authenticate = AsyncMock(
        return_value=Credentials(_ACCOUNT_TOKEN, "user-9", 9999)
    )
    return auth


async def test_mints_token_with_minimal_control_scope() -> None:
    session = FakeSession([_issue_response()])
    sst = SstAuthenticator(_authenticator(), session)

    token = await sst.async_get_token(_device_info())

    assert token == _SST
    assert len(session.calls) == 1
    url, kwargs = session.calls[0]
    assert url == f"https://api-base.dc-na.ww.ecouser.net{SST_ISSUE_PATH}"
    assert kwargs["headers"]["Authorization"] == f"Bearer {_ACCOUNT_TOKEN}"
    payload = kwargs["json"]
    assert payload["sub"] == "user-9"
    assert payload["exp"] == 600
    policy = payload["acl"][0]["policy"][0]
    assert policy["obj"] == [f"Endpoint:q287s6:{_DID}"]
    assert policy["perms"] == ["Control"]


async def test_caches_token_per_device() -> None:
    session = FakeSession([_issue_response(), _issue_response("SST.second")])
    sst = SstAuthenticator(_authenticator(), session)

    first = await sst.async_get_token(_device_info())
    second = await sst.async_get_token(_device_info())

    assert first == second == _SST
    assert len(session.calls) == 1


async def test_invalidate_forces_remint() -> None:
    session = FakeSession([_issue_response(), _issue_response("SST.second")])
    sst = SstAuthenticator(_authenticator(), session)

    await sst.async_get_token(_device_info())
    sst.invalidate(_DID)
    second = await sst.async_get_token(_device_info())

    assert second == "SST.second"
    assert len(session.calls) == 2


async def test_expired_token_is_reminted() -> None:
    session = FakeSession([_issue_response(), _issue_response("SST.second")])
    sst = SstAuthenticator(_authenticator(), session)

    with patch("deebot_client.sst_authentication.time.time", return_value=1000.0):
        await sst.async_get_token(_device_info())
    with patch("deebot_client.sst_authentication.time.time", return_value=1_000_000.0):
        second = await sst.async_get_token(_device_info())

    assert second == "SST.second"
    assert len(session.calls) == 2


async def test_token_is_never_logged() -> None:
    session = FakeSession([_issue_response()])
    sst = SstAuthenticator(_authenticator(), session)

    with LogCapture() as log:
        await sst.async_get_token(_device_info())

    for record in log.records:
        assert _SST not in record.getMessage()
        assert _ACCOUNT_TOKEN not in record.getMessage()


def test_missing_service_block_raises() -> None:
    session = FakeSession([_issue_response()])
    sst = SstAuthenticator(_authenticator(), session)
    info: ApiDeviceInfo = {  # type: ignore[typeddict-item]
        "class": "q287s6",
        "did": _DID,
        "resource": "res9",
    }

    with pytest.raises(KeyError):
        sst._sst_issue_base_url(info)
