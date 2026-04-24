"""Library router — surfaces master library stats and last scan metadata."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cratekeeper_api.db import get_db
from cratekeeper_api.orm import EventTrack, LibraryTrack
from cratekeeper_api.routers._auth import AuthDep

router = APIRouter(prefix="/library", tags=["library"], dependencies=[AuthDep])


class BucketCount(BaseModel):
    bucket: str
    count: int


class LibraryStats(BaseModel):
    total_local_tracks: int
    with_isrc: int
    formats: dict[str, int]
    matched_event_tracks: int
    bucket_distribution: list[BucketCount]


@router.get("/stats", response_model=LibraryStats)
async def library_stats(db: Session = Depends(get_db)) -> LibraryStats:
    total = db.execute(select(func.count(LibraryTrack.path))).scalar_one()
    with_isrc = db.execute(select(func.count(LibraryTrack.path)).where(LibraryTrack.isrc.is_not(None))).scalar_one()
    formats_rows = db.execute(
        select(LibraryTrack.format, func.count(LibraryTrack.path))
        .group_by(LibraryTrack.format)
    ).all()
    formats = {(f or "unknown"): n for f, n in formats_rows}

    matched = db.execute(
        select(func.count(EventTrack.id)).where(EventTrack.local_path.is_not(None))
    ).scalar_one()
    bucket_rows = db.execute(
        select(EventTrack.bucket, func.count(EventTrack.id))
        .where(EventTrack.bucket.is_not(None))
        .group_by(EventTrack.bucket)
        .order_by(func.count(EventTrack.id).desc())
    ).all()
    return LibraryStats(
        total_local_tracks=total,
        with_isrc=with_isrc,
        formats=formats,
        matched_event_tracks=matched,
        bucket_distribution=[BucketCount(bucket=b or "—", count=n) for b, n in bucket_rows],
    )
