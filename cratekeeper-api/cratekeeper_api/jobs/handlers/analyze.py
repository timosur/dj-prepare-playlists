"""`analyze` job — extract BPM / energy / mood for matched event tracks.

Wraps `cratekeeper.mood_analyzer.analyze_track` per track so we can checkpoint
between files (heavy job, may run for a while). Skips tracks already analyzed
(BPM present) unless `force=true`.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import select

from cratekeeper_api.jobs.context import JobContext
from cratekeeper_api.jobs.registry import register
from cratekeeper_api.orm import EventTrack


@register("analyze-mood", heavy=True)
async def run(ctx: JobContext) -> dict:
    event_id = ctx.event_id
    if not event_id:
        raise ValueError("analyze job requires event_id")
    force = bool(ctx.params.get("force", False))
    use_tf = bool(ctx.params.get("use_tf", True))

    # Lazy import — essentia + TF are heavy
    try:
        from cratekeeper.mood_analyzer import _classify_energy, _remap_path, analyze_track
    except Exception as e:
        raise RuntimeError(f"mood_analyzer unavailable: {e}") from e

    with ctx.db_session() as db:
        rows = db.execute(
            select(EventTrack).where(EventTrack.event_id == event_id, EventTrack.local_path.is_not(None))
        ).scalars().all()
        candidates = [(r.id, r.spotify_id, r.local_path, r.bpm) for r in rows]

    if not force:
        candidates = [c for c in candidates if c[3] is None]

    total = len(candidates)
    ctx.log(f"analyzing {total} tracks (use_tf={use_tf}, force={force})")
    analyzed = 0
    failed = 0
    energy_dist = {"low": 0, "mid": 0, "high": 0}

    for i, (row_id, spotify_id, local_path, _) in enumerate(candidates, 1):
        if ctx.cancel_requested:
            break
        path = _remap_path(local_path)
        if not Path(path).exists():
            failed += 1
            continue
        try:
            features = await asyncio.to_thread(analyze_track, path, None, use_tf)
        except Exception as e:
            ctx.log(f"failed: {Path(path).name} — {e}", level="warn")
            failed += 1
            continue

        with ctx.db_session() as db:
            et = db.get(EventTrack, row_id)
            if et is None:
                continue
            et.bpm = features.bpm
            et.key = features.key
            et.danceability = features.danceability
            et.audio_energy = features.energy
            energy_label = _classify_energy(features.energy)
            et.energy = et.energy or energy_label
            et.audio_mood = {
                "happy": features.mood_happy,
                "party": features.mood_party,
                "relaxed": features.mood_relaxed,
                "sad": features.mood_sad,
                "aggressive": features.mood_aggressive,
            }
            et.arousal = features.arousal
            et.valence = features.valence
            energy_dist[energy_label] = energy_dist.get(energy_label, 0) + 1
            analyzed += 1

        ctx.progress(i, total, item={"track_id": spotify_id, "display": Path(path).name})
        ctx.save_checkpoint(spotify_id, {"bpm": features.bpm, "energy": features.energy})

    return {
        "analyzed": analyzed,
        "failed": failed,
        "total": total,
        "energy_distribution": energy_dist,
    }
