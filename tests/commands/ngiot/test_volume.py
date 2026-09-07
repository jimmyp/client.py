"""ngiot volume command tests."""

from __future__ import annotations

from deebot_client.commands.ngiot.volume import SetVolume
from deebot_client.events import VolumeEvent

from . import assert_command, ngiot_response


async def test_SetVolume() -> None:
    await assert_command(
        SetVolume(5),
        ngiot_response(),
        VolumeEvent(5, maximum=None),
        expected_apn=50023,
        expected_data={"volume": 5},
    )
