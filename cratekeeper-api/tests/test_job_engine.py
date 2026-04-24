"""Async job engine unit tests — semaphore + checkpoint behaviour."""

from __future__ import annotations

import asyncio
import time

import pytest

from cratekeeper_api.db import session_scope
from cratekeeper_api.jobs.context import JobContext
from cratekeeper_api.jobs.engine import get_engine, reset_engine
from cratekeeper_api.jobs.registry import register
from cratekeeper_api.orm import JobCheckpoint, JobRun


@pytest.fixture(autouse=True)
def _engine_reset():
    reset_engine()
    yield
    reset_engine()


def _seed_job(job_type: str, params=None) -> str:
    with session_scope() as db:
        j = JobRun(type=job_type, params=params or {}, status="queued")
        db.add(j)
        db.flush()
        return j.id


@pytest.mark.asyncio
async def test_heavy_jobs_serialize():
    started, finished = [], []

    @register("test-heavy", heavy=True)
    async def _h(ctx: JobContext) -> dict:
        started.append(time.monotonic())
        await asyncio.sleep(0.1)
        finished.append(time.monotonic())
        return {"ok": True}

    j1 = _seed_job("test-heavy")
    j2 = _seed_job("test-heavy")
    eng = get_engine()
    eng.submit(j1, None, "test-heavy", {})
    eng.submit(j2, None, "test-heavy", {})
    await eng.wait(j1, timeout=2.0)
    await eng.wait(j2, timeout=2.0)
    assert started[1] >= finished[0] - 0.01  # second only starts after first finishes


@pytest.mark.asyncio
async def test_checkpoint_persists():
    @register("test-cp")
    async def _h(ctx: JobContext) -> dict:
        ctx.save_checkpoint("a", {"v": 1})
        ctx.save_checkpoint("b", {"v": 2})
        return {}

    jid = _seed_job("test-cp")
    eng = get_engine()
    eng.submit(jid, None, "test-cp", {})
    await eng.wait(jid, timeout=2.0)
    with session_scope() as db:
        rows = db.query(JobCheckpoint).filter_by(job_id=jid).all()
        assert {r.key for r in rows} == {"a", "b"}


@pytest.mark.asyncio
async def test_failure_marks_status():
    @register("test-fail")
    async def _h(ctx: JobContext) -> dict:
        raise RuntimeError("boom")

    jid = _seed_job("test-fail")
    eng = get_engine()
    eng.submit(jid, None, "test-fail", {})
    await eng.wait(jid, timeout=2.0)
    with session_scope() as db:
        row = db.get(JobRun, jid)
        assert row.status == "failed"
        assert row.error["code"] == "RuntimeError"
