"""Events router — CRUD + tracks + quality + refetch."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from cratekeeper_api.db import get_db
from cratekeeper_api.orm import Event, EventTrack
from cratekeeper_api.routers._auth import AuthDep
from cratekeeper_api.schemas import (
    EventCreate,
    EventOut,
    EventTrackOut,
    EventTrackPatch,
    EventUpdate,
    QualityReport,
    TrackBulkAction,
)
from cratekeeper_api.services import quality
from cratekeeper_api.services.slug import slugify

router = APIRouter(prefix="/events", tags=["events"], dependencies=[AuthDep])


def _to_out(ev: Event, count: int = 0) -> EventOut:
    return EventOut(
        id=ev.id,
        name=ev.name,
        slug=ev.slug,
        date=ev.date,
        source_playlist_url=ev.source_playlist_url,
        source_playlist_id=ev.source_playlist_id,
        source_playlist_name=ev.source_playlist_name,
        build_mode=ev.build_mode,
        created_at=ev.created_at,
        updated_at=ev.updated_at,
        track_count=count,
    )


@router.get("", response_model=list[EventOut])
async def list_events(db: Session = Depends(get_db)) -> list[EventOut]:
    rows = db.execute(
        select(Event, func.count(EventTrack.id))
        .outerjoin(EventTrack, EventTrack.event_id == Event.id)
        .group_by(Event.id)
        .order_by(Event.created_at.desc())
    ).all()
    return [_to_out(ev, n) for ev, n in rows]


@router.post("", response_model=EventOut, status_code=201)
async def create_event(body: EventCreate, db: Session = Depends(get_db)) -> EventOut:
    slug = slugify(body.slug or body.name)
    # uniquify
    base = slug
    n = 1
    while db.execute(select(Event).where(Event.slug == slug)).scalar_one_or_none():
        n += 1
        slug = f"{base}-{n}"
    ev = Event(
        name=body.name,
        slug=slug,
        date=body.date,
        source_playlist_url=body.source_playlist_url,
        build_mode=body.build_mode,
    )
    db.add(ev)
    try:
        db.flush()
    except IntegrityError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return _to_out(ev)


@router.get("/{event_id}", response_model=EventOut)
async def get_event(event_id: str, db: Session = Depends(get_db)) -> EventOut:
    ev = db.get(Event, event_id)
    if ev is None:
        raise HTTPException(404, "event not found")
    n = db.execute(select(func.count(EventTrack.id)).where(EventTrack.event_id == event_id)).scalar_one()
    return _to_out(ev, n)


@router.patch("/{event_id}", response_model=EventOut)
async def update_event(event_id: str, body: EventUpdate, db: Session = Depends(get_db)) -> EventOut:
    ev = db.get(Event, event_id)
    if ev is None:
        raise HTTPException(404, "event not found")
    if body.name is not None:
        ev.name = body.name
    if body.date is not None:
        ev.date = body.date
    if body.slug is not None:
        ev.slug = slugify(body.slug)
    if body.build_mode is not None:
        ev.build_mode = body.build_mode
    return _to_out(ev)


@router.delete("/{event_id}", status_code=204)
async def delete_event(event_id: str, confirm: bool = Query(False), db: Session = Depends(get_db)) -> None:
    if not confirm:
        raise HTTPException(412, "missing ?confirm=true")
    ev = db.get(Event, event_id)
    if ev is None:
        raise HTTPException(404, "event not found")
    db.delete(ev)


# ----- tracks -----------------------------------------------------------


@router.get("/{event_id}/tracks", response_model=list[EventTrackOut])
async def list_tracks(
    event_id: str,
    confidence: str | None = None,
    bucket: str | None = None,
    match_status: str | None = None,
    acquire_later: bool | None = None,
    limit: int = 500,
    db: Session = Depends(get_db),
) -> list[EventTrackOut]:
    q = select(EventTrack).where(EventTrack.event_id == event_id)
    if confidence:
        q = q.where(EventTrack.confidence == confidence)
    if bucket:
        q = q.where(EventTrack.bucket == bucket)
    if match_status:
        q = q.where(EventTrack.match_status == match_status)
    if acquire_later is not None:
        q = q.where(EventTrack.acquire_later == acquire_later)
    # Low-confidence first (review default)
    q = q.order_by(
        (EventTrack.confidence == "low").desc(),
        (EventTrack.confidence == "medium").desc(),
        EventTrack.name,
    ).limit(limit)
    rows = db.execute(q).scalars().all()
    return [EventTrackOut.model_validate(r) for r in rows]


@router.patch("/{event_id}/tracks/{track_id}", response_model=EventTrackOut)
async def patch_track(event_id: str, track_id: str, body: EventTrackPatch, db: Session = Depends(get_db)) -> EventTrackOut:
    row = db.get(EventTrack, track_id)
    if row is None or row.event_id != event_id:
        raise HTTPException(404, "track not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    return EventTrackOut.model_validate(row)


@router.post("/{event_id}/tracks/bulk", response_model=int)
async def bulk_action(event_id: str, body: TrackBulkAction, db: Session = Depends(get_db)) -> int:
    rows = db.execute(
        select(EventTrack).where(EventTrack.event_id == event_id, EventTrack.id.in_(body.track_ids))
    ).scalars().all()
    n = 0
    for r in rows:
        if body.action == "rebucket":
            if not body.bucket:
                raise HTTPException(400, "bucket required for rebucket")
            r.bucket = body.bucket
            r.confidence = "high"
            n += 1
        elif body.action == "set_acquire_later":
            r.acquire_later = bool(body.acquire_later)
            n += 1
        elif body.action == "accept_genre_suggestion":
            if r.llm_genre_suggestion:
                r.bucket = r.llm_genre_suggestion
                r.confidence = "high"
                r.llm_genre_suggestion_status = "accepted"
                n += 1
        elif body.action == "ignore_genre_suggestion":
            r.llm_genre_suggestion_status = "ignored"
            n += 1
    return n


@router.get("/{event_id}/quality-checks", response_model=QualityReport)
async def quality_checks(event_id: str, db: Session = Depends(get_db)) -> QualityReport:
    try:
        return quality.compute(db, event_id)
    except KeyError:
        raise HTTPException(404, "event not found")


# ----- builds + sync runs ------------------------------------------------


@router.get("/{event_id}/builds")
async def list_builds(event_id: str, db: Session = Depends(get_db)) -> list[dict]:
    from cratekeeper_api.orm import EventBuild
    rows = db.execute(
        select(EventBuild).where(EventBuild.event_id == event_id).order_by(EventBuild.last_built_at.desc())
    ).scalars().all()
    return [
        {
            "id": r.id,
            "kind": r.kind,
            "path": r.path,
            "is_stale": r.is_stale,
            "last_built_at": r.last_built_at,
            "summary": r.summary,
        }
        for r in rows
    ]


@router.get("/{event_id}/sync-runs")
async def list_sync_runs(event_id: str, db: Session = Depends(get_db)) -> list[dict]:
    from cratekeeper_api.orm import PlaylistSyncRun
    rows = db.execute(
        select(PlaylistSyncRun).where(PlaylistSyncRun.event_id == event_id).order_by(PlaylistSyncRun.created_at.desc())
    ).scalars().all()
    return [
        {
            "id": r.id,
            "platform": r.platform,
            "job_id": r.job_id,
            "summary": r.summary,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.get("/{event_id}/tidal-urls")
async def tidal_urls(event_id: str, db: Session = Depends(get_db)) -> dict:
    """Return the Tidal purchase URL for each unmatched ISRC (best-effort)."""
    from cratekeeper_api.container import get_container
    rows = db.execute(
        select(EventTrack).where(
            EventTrack.event_id == event_id,
            EventTrack.match_status == "missing",
            EventTrack.isrc.is_not(None),
        )
    ).scalars().all()
    isrcs = sorted({r.isrc for r in rows if r.isrc})
    tidal = get_container().tidal
    out: dict[str, str | None] = {}
    for isrc in isrcs:
        try:
            out[isrc] = tidal.url_by_isrc(isrc)
        except Exception:
            out[isrc] = None
    return {"urls": out, "count": len([v for v in out.values() if v])}
