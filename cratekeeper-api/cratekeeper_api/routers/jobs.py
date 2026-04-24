"""Jobs router — enqueue / list / detail / cancel + SSE streams."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from cratekeeper_api.db import get_db
from cratekeeper_api.jobs.dependencies import (
    PIPELINE_DEPENDENCIES,
    missing_prerequisites,
)
from cratekeeper_api.jobs.engine import get_engine
from cratekeeper_api.jobs.registry import all_types, get as get_spec
from cratekeeper_api.jobs.sse import (
    event_channel,
    get_hub,
    log_channel,
    progress_channel,
)
from cratekeeper_api.orm import Event, JobRun
from cratekeeper_api.routers._auth import AuthDep
from cratekeeper_api.schemas import JobEnqueue, JobOut

router = APIRouter(tags=["jobs"], dependencies=[AuthDep])


def _enqueue(db: Session, event_id: str | None, body: JobEnqueue) -> JobRun:
    if get_spec(body.type) is None:
        raise HTTPException(400, f"unknown job type: {body.type}. Known: {all_types()}")
    if event_id and not db.get(Event, event_id):
        raise HTTPException(404, "event not found")
    if event_id:
        missing = missing_prerequisites(db, event_id, body.type)
        if missing:
            raise HTTPException(
                409,
                f"cannot enqueue '{body.type}': missing successful prerequisite job(s): "
                f"{', '.join(missing)}",
            )
    job = JobRun(event_id=event_id, type=body.type, params=body.params, status="queued")
    db.add(job)
    db.flush()
    job_id = job.id
    from cratekeeper_api.services.audit import record
    record(
        action="job.submit",
        target_kind="job",
        target_id=job_id,
        payload={"type": body.type, "event_id": event_id, "params": body.params},
        db=db,
    )
    db.commit()  # commit so the engine sees the row
    get_engine().submit(job_id=job_id, event_id=event_id, job_type=body.type, params=body.params)
    return job


@router.post("/events/{event_id}/jobs", response_model=JobOut, status_code=202)
async def enqueue_event_job(event_id: str, body: JobEnqueue, db: Session = Depends(get_db)) -> JobOut:
    job = _enqueue(db, event_id, body)
    return JobOut.model_validate(job)


@router.post("/jobs", response_model=JobOut, status_code=202)
async def enqueue_job(body: JobEnqueue, db: Session = Depends(get_db)) -> JobOut:
    job = _enqueue(db, None, body)
    return JobOut.model_validate(job)


@router.get("/jobs", response_model=list[JobOut])
async def list_jobs(
    event_id: str | None = None,
    type: str | None = None,
    status: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[JobOut]:
    q = select(JobRun).order_by(JobRun.created_at.desc()).limit(limit)
    if event_id:
        q = q.where(JobRun.event_id == event_id)
    if type:
        q = q.where(JobRun.type == type)
    if status:
        q = q.where(JobRun.status == status)
    return [JobOut.model_validate(r) for r in db.execute(q).scalars().all()]


@router.get("/jobs/dependencies")
async def job_dependencies() -> dict[str, list[str]]:
    """Return the pipeline DAG: ``job_type -> [prerequisite job_types]``.

    Used by the UI to disable steps whose prerequisites have not yet succeeded
    for the current event.
    """
    return PIPELINE_DEPENDENCIES


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(job_id: str, db: Session = Depends(get_db)) -> JobOut:
    row = db.get(JobRun, job_id)
    if row is None:
        raise HTTPException(404, "job not found")
    return JobOut.model_validate(row)


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
async def cancel_job(job_id: str, db: Session = Depends(get_db)) -> JobOut:
    row = db.get(JobRun, job_id)
    if row is None:
        raise HTTPException(404, "job not found")
    get_engine().cancel(job_id)
    from cratekeeper_api.services.audit import record
    record(action="job.cancel", target_kind="job", target_id=job_id, db=db)
    return JobOut.model_validate(row)


@router.post("/jobs/{job_id}/resume", response_model=JobOut, status_code=202)
async def resume_job(job_id: str, db: Session = Depends(get_db)) -> JobOut:
    row = db.get(JobRun, job_id)
    if row is None:
        raise HTTPException(404, "job not found")
    if row.status not in ("failed", "cancelled"):
        raise HTTPException(409, f"cannot resume job in status {row.status}")
    row.status = "queued"
    row.error = None
    from cratekeeper_api.services.audit import record
    record(
        action="job.resume",
        target_kind="job",
        target_id=job_id,
        payload={"type": row.type, "event_id": row.event_id},
        db=db,
    )
    db.commit()
    get_engine().submit(job_id=row.id, event_id=row.event_id, job_type=row.type, params=row.params)
    return JobOut.model_validate(row)


# ----- SSE -----------------------------------------------------------------


async def _sse_iter(channel: str, request: Request, last_event_id: int | None):
    hub = get_hub()
    async for evt in hub.subscribe(channel, last_event_id=last_event_id):
        if await request.is_disconnected():
            break
        yield {"event": evt.event, "id": str(evt.id), "data": _json(evt.data)}


def _json(data) -> str:
    import json
    return json.dumps(data, default=str)


@router.get("/jobs/{job_id}/events/progress")
async def stream_progress(job_id: str, request: Request, last_event_id: int | None = Query(default=None, alias="last-event-id")):
    return EventSourceResponse(_sse_iter(progress_channel(job_id), request, last_event_id))


@router.get("/jobs/{job_id}/events/log")
async def stream_log(job_id: str, request: Request, last_event_id: int | None = Query(default=None, alias="last-event-id")):
    return EventSourceResponse(_sse_iter(log_channel(job_id), request, last_event_id))


@router.get("/events/{event_id}/jobs/stream")
async def stream_event_jobs(event_id: str, request: Request, last_event_id: int | None = Query(default=None, alias="last-event-id")):
    return EventSourceResponse(_sse_iter(event_channel(event_id), request, last_event_id))


# ----- Test helper ---------------------------------------------------------


@router.post("/jobs/{job_id}/_wait", include_in_schema=False)
async def _wait(job_id: str, timeout: float = 10.0) -> dict:
    """Test helper: block until job finishes (or timeout). Not part of the public API."""
    try:
        await get_engine().wait(job_id, timeout=timeout)
    except asyncio.TimeoutError:
        return {"status": "timeout"}
    return {"status": "done"}
