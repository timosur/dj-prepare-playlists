"""`match` job — match `event_tracks` against the local `tracks` index.

Persists `local_path` + `match_status` per track. Surfaces a Tidal purchase
URL list for unmatched ISRCs (resolved on demand by the frontend).
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from cratekeeper.matcher import match_tracks
from cratekeeper.models import Track
from cratekeeper_api.config import get_settings
from cratekeeper_api.jobs.context import JobContext
from cratekeeper_api.jobs.registry import register
from cratekeeper_api.orm import EventTrack


def _to_cli(et: EventTrack) -> Track:
    return Track(
        id=et.spotify_id,
        name=et.name,
        artists=list(et.artists),
        artist_ids=list(et.artist_ids),
        album=et.album or "",
        duration_ms=et.duration_ms,
        isrc=et.isrc,
        release_year=et.release_year,
        artist_genres=list(et.artist_genres),
    )


@register("match")
async def run(ctx: JobContext) -> dict:
    event_id = ctx.event_id
    if not event_id:
        raise ValueError("match job requires event_id")

    threshold = int(ctx.params.get("fuzzy_threshold", 85))
    db_url = get_settings().db_url.replace("postgresql+psycopg://", "postgresql://", 1)

    with ctx.db_session() as db:
        rows = db.execute(select(EventTrack).where(EventTrack.event_id == event_id)).scalars().all()

    cli_tracks = [_to_cli(r) for r in rows]
    total = len(cli_tracks)
    ctx.log(f"matching {total} tracks against local library (fuzzy ≥ {threshold})")

    counts = {"isrc": 0, "exact": 0, "fuzzy": 0, "none": 0}

    def cb(i, n, track, result):
        counts[result.method] = counts.get(result.method, 0) + 1
        ctx.progress(i, n, item={
            "track_id": track.id,
            "display": f'"{track.name}" by {", ".join(track.artists)}',
            "match": result.method,
        })

    def _do():
        return match_tracks(cli_tracks, db_url=db_url, fuzzy_threshold=threshold, progress_callback=cb)

    results = await asyncio.to_thread(_do)
    by_id = {r.track.id: r for r in results}

    with ctx.db_session() as db:
        for et in db.execute(select(EventTrack).where(EventTrack.event_id == event_id)).scalars():
            r = by_id.get(et.spotify_id)
            if r is None:
                continue
            et.local_path = r.local_path
            et.match_status = "missing" if r.method == "none" else r.method
            ctx.save_checkpoint(et.spotify_id, {"match": r.method, "local_path": r.local_path})

    return {"total": total, **counts}
