"""SSE pub/sub semantics."""

from __future__ import annotations

import asyncio

import pytest

from cratekeeper_api.jobs.sse import SSEHub


@pytest.mark.asyncio
async def test_replay_after_last_event_id():
    hub = SSEHub()
    hub.publish("c", "log", {"i": 1})
    hub.publish("c", "log", {"i": 2})
    hub.publish("c", "log", {"i": 3})

    received = []

    async def consume():
        async for evt in hub.subscribe("c", last_event_id=1, heartbeat_s=0.05):
            received.append(evt.data["i"])
            if len(received) == 2:
                break

    task = asyncio.create_task(consume())
    await asyncio.wait_for(task, timeout=1.0)
    assert received == [2, 3]


@pytest.mark.asyncio
async def test_live_event_delivery():
    hub = SSEHub()
    received = []

    async def consume():
        async for evt in hub.subscribe("live", heartbeat_s=0.05):
            if evt.event == "log":
                received.append(evt.data["i"])
                if len(received) == 2:
                    return

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.05)
    hub.publish("live", "log", {"i": 10})
    hub.publish("live", "log", {"i": 11})
    await asyncio.wait_for(task, timeout=1.0)
    assert received == [10, 11]
