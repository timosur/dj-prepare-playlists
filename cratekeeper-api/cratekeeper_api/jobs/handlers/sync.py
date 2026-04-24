"""`sync-spotify` / `sync-tidal` jobs — create/update an event sub-playlist."""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from cratekeeper_api.container import get_container
from cratekeeper_api.jobs.context import JobContext
from cratekeeper_api.jobs.registry import register
from cratekeeper_api.orm import Event, EventTrack, PlaylistSyncRun


@register("sync-spotify")
async def sync_spotify(ctx: JobContext) -> dict:
    event_id = ctx.event_id
    if not event_id:
        raise ValueError("sync-spotify requires event_id")

    with ctx.db_session() as db:
        ev = db.get(Event, event_id)
        if ev is None:
            raise ValueError("event not found")
        rows = db.execute(
            select(EventTrack).where(EventTrack.event_id == event_id, EventTrack.match_status.is_not(None))
        ).scalars().all()
        track_ids = [r.spotify_id for r in rows if r.match_status != "missing"]

    if not track_ids:
        return {"created": 0, "added": 0, "playlist_id": None, "reason": "no matched tracks"}

    sp_adapter = get_container().spotify
    # Dynamic capability check — LiveSpotifyAdapter exposes the spotipy client lazily.
    try:
        from cratekeeper.spotify_client import (
            add_tracks_to_playlist,
            create_playlist,
            get_spotify_client,
        )
    except Exception as e:
        raise RuntimeError(f"spotify client unavailable: {e}") from e

    name = ctx.params.get("name") or f"[crate] {ev.name}"
    description = ctx.params.get("description") or f"Cratekeeper event: {ev.slug}"

    def _do():
        sp = get_spotify_client()
        pid = create_playlist(sp, name, description=description)
        add_tracks_to_playlist(sp, pid, track_ids)
        return pid

    ctx.log(f"creating Spotify playlist '{name}' with {len(track_ids)} tracks")
    pid = await asyncio.to_thread(_do)
    ctx.progress(len(track_ids), len(track_ids))

    summary = {"playlist_id": pid, "added": len(track_ids), "name": name}
    with ctx.db_session() as db:
        db.add(PlaylistSyncRun(event_id=event_id, platform="spotify", job_id=ctx.job_id, summary=summary))
        from cratekeeper_api.services.audit import record
        record(action="sync.spotify", target_kind="event", target_id=event_id, payload=summary, db=db)
    # Surface a click-through URL in the summary for the UI
    summary["url"] = f"https://open.spotify.com/playlist/{pid}"
    _ = sp_adapter  # silence unused; the live adapter is what proves credentials work
    return summary


@register("sync-tidal")
async def sync_tidal(ctx: JobContext) -> dict:
    event_id = ctx.event_id
    if not event_id:
        raise ValueError("sync-tidal requires event_id")

    with ctx.db_session() as db:
        ev = db.get(Event, event_id)
        if ev is None:
            raise ValueError("event not found")
        rows = db.execute(
            select(EventTrack).where(EventTrack.event_id == event_id, EventTrack.isrc.is_not(None))
        ).scalars().all()
        isrcs = sorted({r.isrc for r in rows if r.isrc})

    if not isrcs:
        return {"added": 0, "failed": 0, "playlist_id": None, "reason": "no ISRCs"}

    try:
        from cratekeeper.tidal_client import (
            add_tracks_by_isrc,
            create_playlist,
            get_tidal_session,
        )
    except Exception as e:
        raise RuntimeError(f"tidal client unavailable: {e}") from e

    name = ctx.params.get("name") or f"[crate] {ev.name}"
    description = ctx.params.get("description") or f"Cratekeeper event: {ev.slug}"

    state = {"i": 0}

    def _do():
        s = get_tidal_session()
        pid = create_playlist(s, name, description=description)
        added: list[str] = []
        failed: list[str] = []
        for i, isrc in enumerate(isrcs, 1):
            a, f = add_tracks_by_isrc(s, pid, [isrc])
            added.extend(a)
            failed.extend(f)
            state["i"] = i
        return pid, added, failed

    ctx.log(f"creating Tidal playlist '{name}' with up to {len(isrcs)} ISRCs")
    # Crude progress: the underlying call is sync; emit a poll-based progress
    progress_task = asyncio.create_task(_poll_progress(ctx, state, len(isrcs)))
    try:
        pid, added, failed = await asyncio.to_thread(_do)
    finally:
        progress_task.cancel()

    summary = {"playlist_id": pid, "added": len(added), "failed": len(failed), "name": name,
               "url": f"https://tidal.com/browse/playlist/{pid}"}
    with ctx.db_session() as db:
        db.add(PlaylistSyncRun(event_id=event_id, platform="tidal", job_id=ctx.job_id, summary=summary))
        from cratekeeper_api.services.audit import record
        record(action="sync.tidal", target_kind="event", target_id=event_id, payload=summary, db=db)
    return summary


async def _poll_progress(ctx: JobContext, state: dict, total: int) -> None:
    while True:
        await asyncio.sleep(0.5)
        ctx.progress(state.get("i", 0), total)
