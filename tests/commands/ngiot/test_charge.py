"""ngiot charge command tests."""

from __future__ import annotations

from deebot_client.commands.ngiot.charge import Charge
from deebot_client.events import StateEvent
from deebot_client.models import State

from . import assert_command, ngiot_response


async def test_Charge() -> None:
    await assert_command(
        Charge(),
        ngiot_response(),
        StateEvent(State.RETURNING),
        expected_apn=40013,
        expected_data={"chargeSwitch": True},
    )
