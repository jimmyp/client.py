"""ngiot child lock command."""

from __future__ import annotations

from .common import NgiotGetCommand, NgiotSetCommand
from .state import GetState


class SetChildLock(NgiotSetCommand):
    """Set child lock command."""

    NAME = "setChildLock"
    APN = 50038

    @property
    def get_command(self) -> type[NgiotGetCommand]:
        """Return the corresponding get command."""
        return GetState

    def __init__(self, enable: bool) -> None:
        super().__init__({"childLock": enable})
