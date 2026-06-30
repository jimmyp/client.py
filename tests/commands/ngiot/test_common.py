"""ngiot command base tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from deebot_client.commands.ngiot.common import (
    NgiotExecuteCommand,
    NgiotGetCommand,
)
from deebot_client.events.base import Event
from deebot_client.message import HandlingResult, HandlingState

from . import assert_ngiot_command

if TYPE_CHECKING:
    from deebot_client.event_bus import EventBus


@dataclass(frozen=True)
class _ThingEvent(Event):
    value: int


class _GetThing(NgiotGetCommand):
    NAME = "getThing"
    APN = 10001

    @classmethod
    def _handle_body_data_dict(
        cls, event_bus: EventBus, data: dict[str, Any]
    ) -> HandlingResult:
        event_bus.notify(_ThingEvent(int(data["thing"])))
        return HandlingResult.success()


class _SetThing(NgiotExecuteCommand):
    NAME = "setThing"
    APN = 40008

    def __init__(self, value: int) -> None:
        super().__init__({"thing": value})


def _read_response(data: dict[str, Any] | None) -> dict[str, Any]:
    return {"header": {}, "body": {"data": data, "code": 0, "msg": "ok"}}


async def test_get_command_builds_field_query_and_parses_body_data() -> None:
    await assert_ngiot_command(
        _GetThing(["thing"]),
        _read_response({"thing": 42}),
        _ThingEvent(42),
        expected_apn=10001,
        expected_data={"fields": ["thing"]},
    )


async def test_execute_command_writes_key_values_and_succeeds_on_ok() -> None:
    # writes send body.data={key: value}; response body.data is null
    await assert_ngiot_command(
        _SetThing(1),
        _read_response(None),
        None,
        expected_apn=40008,
        expected_data={"thing": 1},
    )


async def test_execute_command_fails_on_error_envelope() -> None:
    await assert_ngiot_command(
        _SetThing(1),
        {"header": {}, "body": {"data": None, "code": 500, "msg": "fail"}},
        None,
        expected_apn=40008,
        expected_data={"thing": 1},
        handling_result=HandlingResult(HandlingState.FAILED),
    )
