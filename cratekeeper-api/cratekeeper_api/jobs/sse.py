"""SSE pub/sub channels — in-process, per-job ring buffers.

Two channels per job: `progress` and `log`. Plus a per-event fan-out channel
(`/events/{id}/jobs/stream`).
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict, deque
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SSEEvent:
    event: str
    data: dict[str, Any]
    id: int = 0


@dataclass
class _Channel:
    buffer: deque[SSEEvent] = field(default_factory=lambda: deque(maxlen=200))
    subscribers: set[asyncio.Queue] = field(default_factory=set)
    next_id: int = 0


class SSEHub:
    def __init__(self) -> None:
        self._channels: dict[str, _Channel] = defaultdict(_Channel)
        self._lock = asyncio.Lock()

    def publish(self, channel: str, event: str, data: dict[str, Any]) -> None:
        ch = self._channels[channel]
        ch.next_id += 1
        evt = SSEEvent(event=event, data=data, id=ch.next_id)
        ch.buffer.append(evt)
        for q in list(ch.subscribers):
            try:
                q.put_nowait(evt)
            except asyncio.QueueFull:
                pass

    async def subscribe(
        self,
        channel: str,
        last_event_id: int | None = None,
        heartbeat_s: float = 15.0,
    ) -> AsyncGenerator[SSEEvent, None]:
        ch = self._channels[channel]
        q: asyncio.Queue[SSEEvent] = asyncio.Queue(maxsize=512)
        # Replay backlog. If no Last-Event-Id is supplied, replay the entire
        # ring buffer so a late subscriber still sees recent events (logs,
        # progress, status). Buffer is bounded (maxlen=200) so this is cheap.
        cutoff = last_event_id if last_event_id is not None else -1
        for evt in list(ch.buffer):
            if evt.id > cutoff:
                yield evt
        ch.subscribers.add(q)
        try:
            while True:
                try:
                    evt = await asyncio.wait_for(q.get(), timeout=heartbeat_s)
                    yield evt
                except asyncio.TimeoutError:
                    yield SSEEvent(
                        event="heartbeat",
                        data={"ts": _now_iso()},
                        id=0,
                    )
        finally:
            ch.subscribers.discard(q)

    @staticmethod
    def format(evt: SSEEvent) -> str:
        return f"id: {evt.id}\nevent: {evt.event}\ndata: {json.dumps(evt.data, default=str)}\n\n"


_hub = SSEHub()


def get_hub() -> SSEHub:
    return _hub


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z"


def progress_channel(job_id: str) -> str:
    return f"job:{job_id}:progress"


def log_channel(job_id: str) -> str:
    return f"job:{job_id}:log"


def event_channel(event_id: str) -> str:
    return f"event:{event_id}:jobs"
