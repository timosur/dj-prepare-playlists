"""`scan` job — index a local audio root into the `tracks` table.

Wraps `cratekeeper.local_scanner.scan_directory`. Runs synchronously inside
a thread because the CLI scanner is sync. Heavy job (serializes on global
semaphore) since it's filesystem-bound.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from cratekeeper.local_scanner import get_db_stats, scan_directory
from cratekeeper_api.config import get_settings
from cratekeeper_api.jobs.context import JobContext
from cratekeeper_api.jobs.registry import register
from cratekeeper_api.security import get_allowed_roots


def _check_root(db, raw: str) -> Path:
    root = Path(raw).expanduser().resolve()
    allowed = get_allowed_roots(db)
    for a in allowed:
        try:
            root.relative_to(a)
            break
        except ValueError:
            continue
    else:
        raise PermissionError(f"path {root} is outside any allowed FS root")
    if not root.exists():
        raise FileNotFoundError(f"scan root not mounted or missing: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"scan root is not a directory: {root}")
    return root


@register("scan-incremental", heavy=True)
async def run_incremental(ctx: JobContext) -> dict:
    return await _run(ctx, incremental=True)


@register("scan-full", heavy=True)
async def run_full(ctx: JobContext) -> dict:
    return await _run(ctx, incremental=False)


async def _run(ctx: JobContext, *, incremental: bool) -> dict:
    raw = ctx.params.get("root")
    with ctx.db_session() as db:
        if not raw:
            allowed = get_allowed_roots(db)
            if not allowed:
                raise ValueError(
                    "scan job requires `root` param (or configure FS roots in Settings)"
                )
            root = allowed[0]
            ctx.log(f"no root given, defaulting to first allowed FS root: {root}")
        else:
            root = _check_root(db, raw)

    db_url = get_settings().db_url.replace("postgresql+psycopg://", "postgresql://", 1)
    ctx.log(f"scanning {root} (incremental={incremental})")

    state = {"new": 0, "skip": 0, "last": "", "logged": 0}

    def cb(new_count: int, skipped: int, file_path):
        if ctx.cancel_requested:
            # Raised from the worker thread; propagates out of scan_directory.
            raise asyncio.CancelledError()
        state["new"] = new_count
        state["skip"] = skipped
        state["last"] = str(file_path) if file_path else state["last"]
        seen = new_count + skipped
        # We don't know the true total (walk-as-we-go); report as i/i+? for UX.
        ctx.progress(seen, seen,
                     item={"display": Path(state["last"]).name if state["last"] else None})
        # Emit a log line every 50 files so the user sees activity in the UI.
        if seen and seen - state["logged"] >= 50:
            state["logged"] = seen
            ctx.log(f"scanned {seen} files (new={new_count}, skipped={skipped}) — last: {Path(state['last']).name if state['last'] else '?'}")

    def _do():
        return scan_directory(root, db_url=db_url, incremental=incremental, progress_callback=cb)

    conn, new, skipped, updated = await asyncio.to_thread(_do)
    try:
        conn.close()
    except Exception:
        pass

    stats = get_db_stats(db_url)
    ctx.log(f"done — new={new} updated={updated} skipped={skipped} library_total={stats.get('total', 0)}")
    return {
        "root": str(root),
        "new": new,
        "skipped": skipped,
        "updated": updated,
        "library_total": stats.get("total", 0),
        "incremental": incremental,
    }
