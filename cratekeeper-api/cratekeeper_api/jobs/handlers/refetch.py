"""`refetch` job — diff a fresh playlist fetch against current `event_tracks`.

Persists the diff on `event_fetches`. Does NOT mutate event_tracks itself —
caller decides whether to follow up with `fetch` (to ingest added tracks).
"""

from __future__ import annotations

from sqlalchemy import select

from cratekeeper_api.container import get_container
from cratekeeper_api.jobs.context import JobContext
from cratekeeper_api.jobs.registry import register
from cratekeeper_api.orm import Event, EventFetch, EventTrack


@register("refetch")
async def run(ctx: JobContext) -> dict:
    event_id = ctx.event_id
    if not event_id:
        raise ValueError("refetch requires event_id")

    sp = get_container().spotify
    with ctx.db_session() as db:
        event = db.get(Event, event_id)
        if event is None:
            raise ValueError(f"event not found: {event_id}")
        url = ctx.params.get("playlist_url") or event.source_playlist_url
        if not url:
            raise ValueError("no playlist_url available")
        existing_ids = set(
            r[0]
            for r in db.execute(
                select(EventTrack.spotify_id).where(EventTrack.event_id == event_id)
            ).all()
        )

    pid, name, tracks = sp.fetch_playlist(url)
    fetched_ids = {t.id for t in tracks}
    added = sorted(fetched_ids - existing_ids)
    removed = sorted(existing_ids - fetched_ids)
    unchanged = sorted(existing_ids & fetched_ids)

    ctx.log(f"refetch diff: +{len(added)} / -{len(removed)} / ={len(unchanged)}")

    with ctx.db_session() as db:
        fetch_row = EventFetch(
            event_id=event_id,
            added=added,
            removed=removed,
            unchanged=unchanged,
            job_id=ctx.job_id,
        )
        db.add(fetch_row)

    return {"added": len(added), "removed": len(removed), "unchanged": len(unchanged), "playlist_name": name}
