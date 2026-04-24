"""Shared rate limiter for MusicBrainz (1 rps) and any other rate-bound resource."""

from __future__ import annotations

import asyncio
import time


class TokenBucket:
    """Single-rate token bucket. `acquire()` waits until a token is available."""

    def __init__(self, rate_per_sec: float, burst: int = 1) -> None:
        self._rate = rate_per_sec
        self._capacity = burst
        self._tokens = float(burst)
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            self._last = now
            if self._tokens >= 1:
                self._tokens -= 1
                return
            wait_for = (1 - self._tokens) / self._rate
            await asyncio.sleep(wait_for)
            self._tokens = 0
            self._last = time.monotonic()


# Global limiters (single process, in-memory)
MUSICBRAINZ_LIMITER = TokenBucket(rate_per_sec=1.0, burst=1)
