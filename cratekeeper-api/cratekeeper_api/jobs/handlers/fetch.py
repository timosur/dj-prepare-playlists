"""`fetch` job — Spotify playlist intake. Persists/refreshes `event_tracks`."""

from __future__ import annotations

from sqlalchemy import select

from cratekeeper_api.container import get_container
from cratekeeper_api.jobs.context import JobContext
from cratekeeper_api.jobs.registry import register
from cratekeeper_api.orm import Event, EventTrack


@register("fetch")
async def run(ctx: JobContext) -> dict:
    event_id = ctx.event_id
    if not event_id:
        raise ValueError("fetch job requires event_id")

    sp = get_container().spotify
    with ctx.db_session() as db:
        event = db.get(Event, event_id)
        if event is None:
            raise ValueError(f"event not found: {event_id}")
        url_or_id = ctx.params.get("playlist_url") or event.source_playlist_url
        if not url_or_id:
            raise ValueError("no playlist_url available")

    ctx.log(f"fetching playlist {url_or_id}")
    pid, name, tracks = sp.fetch_playlist(url_or_id)
    total = len(tracks)
    ctx.log(f"received {total} tracks from '{name}'")

    new_isrcs = 0
    with ctx.db_session() as db:
        event = db.get(Event, event_id)
        event.source_playlist_id = pid
        event.source_playlist_name = name

        existing = {
            r.spotify_id: r
            for r in db.execute(select(EventTrack).where(EventTrack.event_id == event_id)).scalars()
        }
        for i, t in enumerate(tracks, 1):
            row = existing.get(t.id)
            if row is None:
                row = EventTrack(
                    event_id=event_id,
                    spotify_id=t.id,
                    name=t.name,
                    artists=list(t.artists),
                    artist_ids=list(t.artist_ids),
                    album=t.album,
                    duration_ms=t.duration_ms,
                    isrc=t.isrc,
                    release_year=t.release_year,
                    artist_genres=list(t.artist_genres),
                )
                db.add(row)
                if t.isrc:
                    new_isrcs += 1
            else:
                # Refresh metadata snapshot but keep review state
                row.name = t.name
                row.artists = list(t.artists)
                row.artist_ids = list(t.artist_ids)
                row.album = t.album
                row.duration_ms = t.duration_ms
                row.isrc = t.isrc or row.isrc
                row.release_year = t.release_year or row.release_year
                row.artist_genres = list(t.artist_genres) or row.artist_genres
            ctx.progress(i, total, item={"track_id": t.id, "display": f'"{t.name}" by {", ".join(t.artists)}'})
            ctx.save_checkpoint(t.id, {"action": "ingested"})

    return {"playlist_name": name, "track_count": total, "new_isrc_count": new_isrcs}
