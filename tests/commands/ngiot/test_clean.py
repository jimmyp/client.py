from __future__ import annotations

from typing import Any

import pytest

from deebot_client.commands.ngiot.clean import Charge, Clean
from deebot_client.events import StateEvent
from deebot_client.models import CleanAction, State

from . import assert_ngiot_command

_OK: dict[str, Any] = {"header": {}, "body": {"data": None, "code": 0, "msg": "ok"}}


@pytest.mark.parametrize(
    ("action", "expected_apn", "expected_data", "expected_state"),
    [
        (
            CleanAction.START,
            40008,
            {"cleanSwitch": True, "cleanMode": "cleanBuilding"},
            State.CLEANING,
        ),
        (CleanAction.STOP, 40002, {"cleanSwitch": False}, State.IDLE),
        (CleanAction.PAUSE, 40009, {"pauseSwitch": True}, State.PAUSED),
        (CleanAction.RESUME, 40009, {"pauseSwitch": False}, State.CLEANING),
    ],
)
async def test_Clean_actions(
    action: CleanAction,
    expected_apn: int,
    expected_data: dict[str, Any],
    expected_state: State,
) -> None:
    await assert_ngiot_command(
        Clean(action),
        _OK,
        StateEvent(expected_state),
        expected_apn=expected_apn,
        expected_data=expected_data,
    )


async def test_Charge_returns_to_dock() -> None:
    # Captured: apn 40015 {chargeSwitch: false} == return to dock.
    await assert_ngiot_command(
        Charge(),
        _OK,
        StateEvent(State.RETURNING),
        expected_apn=40015,
        expected_data={"chargeSwitch": False},
    )
