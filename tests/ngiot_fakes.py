"""Shared aiohttp session fakes for ngiot transport tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    from collections.abc import Sequence


class FakeResponse:
    """Fake aiohttp response usable as an async context manager."""

    def __init__(self, payload: bytes, status: int = 200) -> None:
        self._payload = payload
        self.status = status

    async def read(self) -> bytes:
        """Return the raw body."""
        return self._payload

    def raise_for_status(self) -> None:
        """Raise for a non-success status."""
        if self.status >= 400:
            msg = f"HTTP {self.status}"
            raise RuntimeError(msg)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> bool:
        return False


class FakeSession:
    """Fake aiohttp session that records posts and replays canned responses."""

    def __init__(self, responses: Sequence[FakeResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        """Record the call and return the next canned response."""
        self.calls.append((url, kwargs))
        return self._responses.pop(0)
