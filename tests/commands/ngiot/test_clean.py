"""ngiot clean command tests."""

from __future__ import annotations

from typing import Any

import pytest

from deebot_client.commands.ngiot.clean import Clean
from deebot_client.events import StateEvent
from deebot_client.message import HandlingResult, HandlingState
from deebot_client.models import CleanAction, State

from . import assert_command, ngiot_response


@pytest.mark.parametrize(
    ("action", "last_state", "apn", "data", "expected_state"),
    [
        (
            CleanAction.START,
            None,
            40008,
            {"cleanSwitch": True, "cleanMode": "cleanBuilding"},
            State.CLEANING,
        ),
        (
            CleanAction.START,
            State.DOCKED,
            40008,
            {"cleanSwitch": True, "cleanMode": "cleanBuilding"},
            State.CLEANING,
        ),
        # the Home Assistant start button on a paused bot means resume
        (
            CleanAction.START,
            State.PAUSED,
            40011,
            {"pauseSwitch": False},
            State.CLEANING,
        ),
        (
            CleanAction.RESUME,
            State.PAUSED,
            40011,
            {"pauseSwitch": False},
            State.CLEANING,
        ),
        (CleanAction.RESUME, None, 40011, {"pauseSwitch": False}, State.CLEANING),
        (
            CleanAction.RESUME,
            State.DOCKED,
            40008,
            {"cleanSwitch": True, "cleanMode": "cleanBuilding"},
            State.CLEANING,
        ),
        (CleanAction.PAUSE, State.CLEANING, 40009, {"pauseSwitch": True}, State.PAUSED),
        (CleanAction.STOP, State.CLEANING, 40002, {"cleanSwitch": False}, State.IDLE),
        (CleanAction.STOP, State.PAUSED, 40002, {"cleanSwitch": False}, State.IDLE),
    ],
)
async def test_Clean(
    action: CleanAction,
    last_state: State | None,
    apn: int,
    data: dict[str, Any],
    expected_state: State,
) -> None:
    await assert_command(
        Clean(action),
        ngiot_response(),
        StateEvent(expected_state),
        expected_apn=apn,
        expected_data=data,
        last_state=last_state,
    )


async def test_Clean_failure_emits_no_state() -> None:
    await assert_command(
        Clean(CleanAction.START),
        ngiot_response(code=1),
        None,
        expected_apn=40008,
        expected_data={"cleanSwitch": True, "cleanMode": "cleanBuilding"},
        handling_result=HandlingResult(HandlingState.FAILED),
    )
