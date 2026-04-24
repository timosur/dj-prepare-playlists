"""`build-event` job — copy/symlink matched tracks into output_dir/Genre/...

Records the result on `event_builds`.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from cratekeeper.event_builder import build_event_folder
from cratekeeper.models import Track
from cratekeeper_api.jobs.context import JobContext
from cratekeeper_api.jobs.registry import register
from cratekeeper_api.orm import Event, EventBuild, EventTrack
from cratekeeper_api.security import get_allowed_roots


def _to_cli(et: EventTrack) -> Track:
    return Track(
        id=et.spotify_id,
        name=et.name,
        artists=list(et.artists),
        artist_ids=list(et.artist_ids),
        album=et.album or "",
        duration_ms=et.duration_ms,
        bucket=et.bucket,
        local_path=et.local_path,
    )


@register("build-event", heavy=True)
async def run(ctx: JobContext) -> dict:
    event_id = ctx.event_id
    if not event_id:
        raise ValueError("build-event requires event_id")

    raw_out = ctx.params.get("output_dir")
    if not raw_out:
        raise ValueError("output_dir param required")
    dry_run = bool(ctx.params.get("dry_run", False))

    with ctx.db_session() as db:
        ev = db.get(Event, event_id)
        if not ev:
            raise ValueError("event not found")
        out = Path(raw_out).expanduser().resolve()
        allowed = get_allowed_roots(db)
        for a in allowed:
            try:
                out.relative_to(a)
                break
            except ValueError:
                continue
        else:
            raise PermissionError(f"output_dir {out} outside allowed FS roots")

        rows = db.execute(select(EventTrack).where(EventTrack.event_id == event_id)).scalars().all()
        cli_tracks = [_to_cli(r) for r in rows]
        slug = ev.slug
        build_mode = ev.build_mode

    target = out / slug
    ctx.log(f"building event folder at {target} (mode={build_mode}, dry_run={dry_run})")

    if dry_run:
        # Diff-only: count would-copy / missing without touching the FS.
        would_copy = 0
        missing: list[Track] = []
        for i, t in enumerate(cli_tracks, 1):
            ctx.progress(i, len(cli_tracks), item={"track_id": t.id, "display": t.name, "dry_run": True})
            if not t.local_path or not Path(t.local_path).exists():
                missing.append(t)
                continue
            would_copy += 1
        return {
            "output_dir": str(target),
            "would_copy": would_copy,
            "missing": len(missing),
            "total": len(cli_tracks),
            "build_mode": build_mode,
            "dry_run": True,
        }

    target.mkdir(parents=True, exist_ok=True)

    state = {"i": 0}

    def cb(i, n, track, target_path):
        state["i"] = i
        ctx.progress(i, n, item={"track_id": track.id, "display": track.name})

    def _do():
        return build_event_folder(cli_tracks, target, progress_callback=cb)

    created, skipped, missing = await asyncio.to_thread(_do)

    summary = {
        "output_dir": str(target),
        "created": created,
        "skipped": skipped,
        "missing": len(missing),
        "build_mode": build_mode,
    }

    with ctx.db_session() as db:
        # Upsert one EventBuild row of kind=event-folder per event
        existing = db.execute(
            select(EventBuild).where(EventBuild.event_id == event_id, EventBuild.kind == "event-folder")
        ).scalar_one_or_none()
        if existing is None:
            db.add(EventBuild(
                event_id=event_id, kind="event-folder", path=str(target),
                is_stale=False, last_built_at=datetime.now(timezone.utc), summary=summary,
            ))
        else:
            existing.path = str(target)
            existing.is_stale = False
            existing.last_built_at = datetime.now(timezone.utc)
            existing.summary = summary
        from cratekeeper_api.services.audit import record
        record(
            action="build.event",
            target_kind="event",
            target_id=event_id,
            payload=summary,
            db=db,
        )

    return summary


@register("build-library", heavy=True)
async def run_library(ctx: JobContext) -> dict:
    """Build the master library at <output_dir>/Genre/... by copying matched tracks
    from ALL events. Records a global EventBuild with event_id of the triggering event.
    """
    raw_out = ctx.params.get("output_dir")
    if not raw_out:
        raise ValueError("output_dir param required")
    dry_run = bool(ctx.params.get("dry_run", False))

    from cratekeeper.library_builder import build_library

    with ctx.db_session() as db:
        out = Path(raw_out).expanduser().resolve()
        allowed = get_allowed_roots(db)
        for a in allowed:
            try:
                out.relative_to(a)
                break
            except ValueError:
                continue
        else:
            raise PermissionError(f"output_dir {out} outside allowed FS roots")

        rows = db.execute(
            select(EventTrack).where(EventTrack.local_path.is_not(None), EventTrack.bucket.is_not(None))
        ).scalars().all()
        # Dedup by local_path
        seen = set()
        cli_tracks: list[Track] = []
        for r in rows:
            if r.local_path in seen:
                continue
            seen.add(r.local_path)
            cli_tracks.append(_to_cli(r))

    ctx.log(f"building master library at {out} ({len(cli_tracks)} unique tracks, dry_run={dry_run})")

    if dry_run:
        would_copy = 0
        missing_n = 0
        for i, t in enumerate(cli_tracks, 1):
            ctx.progress(i, len(cli_tracks), item={"track_id": t.id, "display": t.name, "dry_run": True})
            if not t.local_path or not Path(t.local_path).exists():
                missing_n += 1
                continue
            would_copy += 1
        return {
            "output_dir": str(out),
            "would_copy": would_copy,
            "missing": missing_n,
            "total": len(cli_tracks),
            "dry_run": True,
        }

    def cb(i, n, track, dest_path):
        ctx.progress(i, n, item={"track_id": track.id, "display": track.name})

    def _do():
        return build_library(cli_tracks, out, progress_callback=cb)

    copied, skipped, missing = await asyncio.to_thread(_do)
    summary = {
        "output_dir": str(out),
        "copied": copied,
        "skipped": skipped,
        "missing": len(missing),
        "total": len(cli_tracks),
    }
    with ctx.db_session() as db:
        from cratekeeper_api.services.audit import record
        record(action="build.library", target_kind="library", target_id=None, payload=summary, db=db)
    return summary
