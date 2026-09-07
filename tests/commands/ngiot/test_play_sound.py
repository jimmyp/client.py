"""ngiot play sound command tests."""

from __future__ import annotations

from deebot_client.commands.ngiot.play_sound import PlaySound

from . import assert_command, ngiot_response


async def test_PlaySound() -> None:
    await assert_command(
        PlaySound(),
        ngiot_response(),
        None,
        expected_apn=40019,
        expected_data={"seek": True},
    )
