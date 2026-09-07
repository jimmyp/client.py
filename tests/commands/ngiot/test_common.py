"""ngiot command base tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from deebot_client.commands.ngiot.common import (
    NgiotExecuteCommand,
    NgiotGetCommand,
    NgiotSetCommand,
)
from deebot_client.events import AvailabilityEvent
from deebot_client.events.base import Event
from deebot_client.message import HandlingResult, HandlingState

from . import assert_command, ngiot_response

if TYPE_CHECKING:
    from deebot_client.event_bus import EventBus


@dataclass(frozen=True)
class _ThingEvent(Event):
    value: int


class _GetThing(NgiotGetCommand):
    NAME = "getThing"
    APN = 10001

    def __init__(self, *, is_available_check: bool = False) -> None:
        super().__init__(["thing"])
        self._is_available_check = is_available_check

    @classmethod
    def _handle_body_data_dict(
        cls, event_bus: EventBus, data: dict[str, Any]
    ) -> HandlingResult:
        event_bus.notify(_ThingEvent(int(data["thing"])))
        return HandlingResult.success()


class _DoThing(NgiotExecuteCommand):
    NAME = "doThing"
    APN = 40008

    def __init__(self, value: int) -> None:
        super().__init__({"thing": value})


class _SetThing(NgiotSetCommand):
    NAME = "setThing"
    APN = 50001
    get_command = _GetThing

    def __init__(self, value: int) -> None:
        super().__init__({"thing": value})


async def test_NgiotGetCommand() -> None:
    await assert_command(
        _GetThing(),
        ngiot_response({"thing": 42}),
        _ThingEvent(42),
        expected_apn=10001,
        expected_data={"fields": ["thing"]},
    )


async def test_NgiotExecuteCommand() -> None:
    await assert_command(
        _DoThing(1),
        ngiot_response(),
        None,
        expected_apn=40008,
        expected_data={"thing": 1},
    )


async def test_NgiotSetCommand_optimistic_event() -> None:
    await assert_command(
        _SetThing(7),
        ngiot_response(),
        _ThingEvent(7),
        expected_apn=50001,
        expected_data={"thing": 7},
    )


async def test_NgiotSetCommand_failure_emits_nothing() -> None:
    await assert_command(
        _SetThing(7),
        ngiot_response(code=1),
        None,
        expected_apn=50001,
        expected_data={"thing": 7},
        handling_result=HandlingResult(HandlingState.FAILED),
    )


@pytest.mark.parametrize("code", [0, "0"])
async def test_NgiotCommand_success_codes(code: int | str) -> None:
    await assert_command(
        _DoThing(1),
        {"code": code, "data": None},
        None,
        expected_apn=40008,
        expected_data={"thing": 1},
    )


async def test_NgiotCommand_offline() -> None:
    await assert_command(
        _DoThing(1),
        ngiot_response(code=4200),
        AvailabilityEvent(available=False),
        expected_apn=40008,
        expected_data={"thing": 1},
        handling_result=HandlingResult(HandlingState.FAILED),
    )


async def test_NgiotCommand_unknown_response_is_analysed() -> None:
    await assert_command(
        _DoThing(1),
        {"ret": "fail"},
        None,
        expected_apn=40008,
        expected_data={"thing": 1},
        handling_result=HandlingResult(HandlingState.ANALYSE_LOGGED),
    )


async def test_NgiotCommand_availability_check_logs_info(
    caplog: pytest.LogCaptureFixture,
) -> None:
    await assert_command(
        _GetThing(is_available_check=True),
        ngiot_response(code=500),
        None,
        expected_apn=10001,
        expected_data={"fields": ["thing"]},
        handling_result=HandlingResult(HandlingState.FAILED),
    )
    records = [r for r in caplog.records if "getThing" in r.getMessage()]
    assert records
    assert all(r.levelname == "INFO" for r in records)


def test_NgiotCommand_apn_override() -> None:
    assert _DoThing(1).apn == 40008
