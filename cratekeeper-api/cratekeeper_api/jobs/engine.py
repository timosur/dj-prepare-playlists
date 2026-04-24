"""In-process asyncio job runner.

Single FastAPI process. One global heavy-job semaphore (capacity 1). Light
jobs cap per-type at 4. Crash recovery is via `JobCheckpoint` rows.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from cratekeeper_api.db import session_scope
from cratekeeper_api.jobs.context import JobContext
from cratekeeper_api.jobs.registry import get as get_spec
from cratekeeper_api.orm import JobRun

log = logging.getLogger(__name__)


class JobEngine:
    def __init__(self, light_concurrency_per_type: int = 4) -> None:
        self._heavy_sem = asyncio.Semaphore(1)
        self._light_sem_per_type: dict[str, asyncio.Semaphore] = {}
        self._light_concurrency = light_concurrency_per_type
        self._tasks: dict[str, asyncio.Task] = {}
        self._contexts: dict[str, JobContext] = {}

    def _light_sem(self, job_type: str) -> asyncio.Semaphore:
        sem = self._light_sem_per_type.get(job_type)
        if sem is None:
            sem = asyncio.Semaphore(self._light_concurrency)
            self._light_sem_per_type[job_type] = sem
        return sem

    def submit(self, job_id: str, event_id: str | None, job_type: str, params: dict) -> None:
        spec = get_spec(job_type)
        if spec is None:
            raise ValueError(f"unknown job type: {job_type}")
        ctx = JobContext(job_id=job_id, event_id=event_id, job_type=job_type, params=params)
        self._contexts[job_id] = ctx
        task = asyncio.create_task(self._run(ctx, spec.heavy), name=f"job:{job_id}")
        self._tasks[job_id] = task

    async def _run(self, ctx: JobContext, heavy: bool) -> None:
        sem = self._heavy_sem if heavy else self._light_sem(ctx.job_type)
        async with sem:
            self._mark(ctx.job_id, status="running", started_at=datetime.now(timezone.utc))
            ctx.stage("running", detail="started")
            try:
                spec = get_spec(ctx.job_type)
                assert spec is not None
                summary = await spec.handler(ctx)
                if ctx.cancel_requested:
                    self._mark(ctx.job_id, status="cancelled", ended_at=datetime.now(timezone.utc), summary=summary or {})
                    ctx.stage("cancelled", summary=summary or {})
                else:
                    self._mark(ctx.job_id, status="succeeded", ended_at=datetime.now(timezone.utc), summary=summary or {})
                    ctx.stage("succeeded", summary=summary or {})
            except asyncio.CancelledError:
                # Handler co-operatively bailed out (e.g. scan thread saw cancel_requested).
                self._mark(ctx.job_id, status="cancelled", ended_at=datetime.now(timezone.utc), summary={"cancelled": True})
                ctx.stage("cancelled", summary={"cancelled": True})
            except Exception as e:  # noqa: BLE001 — boundary
                log.exception("job %s failed", ctx.job_id)
                err = {"code": e.__class__.__name__, "message": str(e)}
                self._mark(ctx.job_id, status="failed", ended_at=datetime.now(timezone.utc), error=err)
                ctx.stage("failed", error=err)
            finally:
                self._tasks.pop(ctx.job_id, None)
                self._contexts.pop(ctx.job_id, None)

    def cancel(self, job_id: str) -> bool:
        ctx = self._contexts.get(job_id)
        if ctx is None:
            return False
        ctx.cancel_requested = True
        return True

    async def wait(self, job_id: str, timeout: float | None = None) -> None:
        task = self._tasks.get(job_id)
        if task is None:
            return
        await asyncio.wait_for(asyncio.shield(task), timeout=timeout)

    async def shutdown(self) -> None:
        for t in list(self._tasks.values()):
            t.cancel()
        for t in list(self._tasks.values()):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass

    def _mark(self, job_id: str, **fields) -> None:
        with session_scope() as db:
            row = db.get(JobRun, job_id)
            if row is None:
                return
            for k, v in fields.items():
                setattr(row, k, v)


_engine: JobEngine | None = None


def get_engine() -> JobEngine:
    global _engine
    if _engine is None:
        _engine = JobEngine()
    return _engine


def reset_engine() -> None:
    global _engine
    _engine = JobEngine()
