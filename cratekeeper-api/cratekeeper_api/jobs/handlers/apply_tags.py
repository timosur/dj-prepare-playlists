"""`apply-tags` job — write LLM tags + bucket + BPM/key into local audio files.

Snapshots original tag bytes into `tag_backups` (created on demand) for undo.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import select, text

from cratekeeper.models import Track
from cratekeeper.tag_writer import tag_track
from cratekeeper_api.jobs.context import JobContext
from cratekeeper_api.jobs.registry import register
from cratekeeper_api.orm import EventTrack


def _ensure_backup_table(db) -> None:
    db.execute(text(
        """
        CREATE TABLE IF NOT EXISTS tag_backups (
            id SERIAL PRIMARY KEY,
            event_id TEXT NOT NULL,
            spotify_id TEXT NOT NULL,
            local_path TEXT NOT NULL,
            backup_path TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    ))


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
        bucket=et.bucket,
        confidence=et.confidence,
        era=et.era,
        local_path=et.local_path,
        bpm=et.bpm,
        key=et.key,
        energy=et.energy,
        function=list(et.function),
        crowd=list(et.crowd),
        mood_tags=list(et.mood_tags),
    )


@register("apply-tags", heavy=True)
async def run(ctx: JobContext) -> dict:
    event_id = ctx.event_id
    if not event_id:
        raise ValueError("apply-tags requires event_id")

    dry_run = bool(ctx.params.get("dry_run", False))

    with ctx.db_session() as db:
        _ensure_backup_table(db)
        rows = db.execute(
            select(EventTrack).where(
                EventTrack.event_id == event_id,
                EventTrack.local_path.is_not(None),
                EventTrack.energy.is_not(None),
            )
        ).scalars().all()
        snapshot = [(r.id, r.spotify_id, _to_cli(r)) for r in rows]

    total = len(snapshot)
    ctx.log(f"writing tags for {total} tracks (dry_run={dry_run})")
    backup_dir = Path.home() / ".cratekeeper" / "tag-backups" / event_id
    backup_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    failed = 0
    for i, (row_id, spotify_id, t) in enumerate(snapshot, 1):
        if ctx.cancel_requested:
            break
        path = Path(t.local_path or "")
        if not path.exists():
            failed += 1
            continue

        if dry_run:
            ctx.progress(i, total, item={"track_id": spotify_id, "display": path.name, "dry_run": True})
            continue

        # Snapshot original bytes (small audio header tag area is hard to isolate
        # cleanly per format; we copy the whole file). Skip if a backup exists.
        backup_path = backup_dir / f"{spotify_id}{path.suffix}"
        if not backup_path.exists():
            try:
                await asyncio.to_thread(_copy_bytes, path, backup_path)
            except Exception as e:
                ctx.log(f"backup failed for {path.name}: {e}", level="warn")
                failed += 1
                continue

        ok = await asyncio.to_thread(tag_track, t)
        if ok:
            written += 1
            with ctx.db_session() as db:
                db.execute(text(
                    "INSERT INTO tag_backups (event_id, spotify_id, local_path, backup_path) "
                    "VALUES (:e, :s, :p, :b)"
                ), {"e": event_id, "s": spotify_id, "p": str(path), "b": str(backup_path)})
        else:
            failed += 1
        ctx.progress(i, total, item={"track_id": spotify_id, "display": path.name, "written": ok})
        ctx.save_checkpoint(spotify_id, {"written": ok})

    # Mark builds stale
    with ctx.db_session() as db:
        from cratekeeper_api.orm import EventBuild
        db.query(EventBuild).filter(EventBuild.event_id == event_id).update({"is_stale": True})
        if not dry_run:
            from cratekeeper_api.services.audit import record
            record(
                action="tags.apply",
                target_kind="event",
                target_id=event_id,
                payload={"written": written, "failed": failed, "total": total},
                db=db,
            )

    return {"written": written, "failed": failed, "total": total, "dry_run": dry_run, "backup_dir": str(backup_dir)}


def _copy_bytes(src: Path, dst: Path) -> None:
    import shutil
    shutil.copy2(str(src), str(dst))


