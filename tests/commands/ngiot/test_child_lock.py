"""ngiot child lock command tests."""

from __future__ import annotations

import pytest

from deebot_client.commands.ngiot.child_lock import SetChildLock
from deebot_client.events import ChildLockEvent

from . import assert_command, ngiot_response


@pytest.mark.parametrize("enable", [True, False])
async def test_SetChildLock(enable: bool) -> None:
    await assert_command(
        SetChildLock(enable),
        ngiot_response(),
        ChildLockEvent(enable),
        expected_apn=50038,
        expected_data={"childLock": enable},
    )
