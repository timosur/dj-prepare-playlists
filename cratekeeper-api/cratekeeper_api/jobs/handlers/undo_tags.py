"""`undo-tags` job — restore audio files from `tag_backups` snapshots.

Reads the `tag_backups` table created on demand by `apply-tags`. For each
backup row, copies the snapshot back over the live file. Supports `dry_run`.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from sqlalchemy import text

from cratekeeper_api.jobs.context import JobContext
from cratekeeper_api.jobs.registry import register


@register("undo-tags", heavy=True)
async def run(ctx: JobContext) -> dict:
    event_id = ctx.event_id
    if not event_id:
        raise ValueError("undo-tags requires event_id")

    dry_run = bool(ctx.params.get("dry_run", False))

    with ctx.db_session() as db:
        # Table is created on demand by apply-tags. Tolerate its absence.
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
        rows = db.execute(text(
            "SELECT id, spotify_id, local_path, backup_path FROM tag_backups "
            "WHERE event_id = :e ORDER BY id DESC"
        ), {"e": event_id}).all()

    total = len(rows)
    ctx.log(f"undoing tag writes for {total} backups (dry_run={dry_run})")

    restored = 0
    missing_backup = 0
    failed = 0
    consumed_ids: list[int] = []

    for i, (backup_id, spotify_id, local_path, backup_path) in enumerate(rows, 1):
        if ctx.cancel_requested:
            break
        live = Path(local_path)
        snap = Path(backup_path)
        if not snap.exists():
            missing_backup += 1
            ctx.progress(i, total, item={"track_id": spotify_id, "display": live.name, "missing_backup": True})
            continue
        if dry_run:
            ctx.progress(i, total, item={"track_id": spotify_id, "display": live.name, "dry_run": True})
            continue
        try:
            await asyncio.to_thread(shutil.copy2, str(snap), str(live))
            restored += 1
            consumed_ids.append(backup_id)
        except Exception as e:
            failed += 1
            ctx.log(f"restore failed for {live.name}: {e}", level="warn")
        ctx.progress(i, total, item={"track_id": spotify_id, "display": live.name, "restored": True})
        ctx.save_checkpoint(spotify_id, {"restored": True})

    if not dry_run and consumed_ids:
        with ctx.db_session() as db:
            db.execute(
                text("DELETE FROM tag_backups WHERE id = ANY(:ids)"),
                {"ids": consumed_ids},
            )
            from cratekeeper_api.orm import EventBuild
            db.query(EventBuild).filter(EventBuild.event_id == event_id).update({"is_stale": True})
            from cratekeeper_api.services.audit import record
            record(
                action="tags.undo",
                target_kind="event",
                target_id=event_id,
                payload={"restored": restored, "failed": failed, "missing_backup": missing_backup},
                db=db,
            )

    return {
        "restored": restored,
        "failed": failed,
        "missing_backup": missing_backup,
        "total": total,
        "dry_run": dry_run,
    }
