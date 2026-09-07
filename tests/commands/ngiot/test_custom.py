"""ngiot custom command tests."""

from __future__ import annotations

from deebot_client.commands.ngiot.custom import CustomCommand
from deebot_client.events import CustomCommandEvent
from deebot_client.message import HandlingResult, HandlingState

from . import assert_command, ngiot_response


async def test_CustomCommand() -> None:
    response = ngiot_response({"battery": 42})
    await assert_command(
        CustomCommand("10001", {"fields": ["battery"]}),
        response,
        CustomCommandEvent("10001", response),
        expected_apn=10001,
        expected_data={"fields": ["battery"]},
    )


async def test_CustomCommand_failure() -> None:
    await assert_command(
        CustomCommand("40019"),
        ngiot_response(code=1),
        None,
        expected_apn=40019,
        expected_data={},
        handling_result=HandlingResult(HandlingState.FAILED),
    )


def test_CustomCommand_equality() -> None:
    assert CustomCommand("10001", {"a": 1}) == CustomCommand("10001", {"a": 1})
    assert CustomCommand("10001", {"a": 1}) != CustomCommand("10002", {"a": 1})
    assert hash(CustomCommand("10001")) != hash(CustomCommand("10002"))
