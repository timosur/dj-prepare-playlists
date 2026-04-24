"""`classify-tags` job — LLM tag classifier (Anthropic).

Mocked by default (see container.set_anthropic). Marks any existing
`event_builds` rows as stale on completion (per plan).
"""

from __future__ import annotations

import json

from sqlalchemy import select, update

from cratekeeper_api.config import get_settings
from cratekeeper_api.container import anthropic_client_for
from cratekeeper_api.jobs.context import JobContext
from cratekeeper_api.jobs.registry import register
from cratekeeper_api.orm import EventBuild, EventTrack

CHUNK_SIZE = 50


@register("classify-tags")
async def run(ctx: JobContext) -> dict:
    event_id = ctx.event_id
    if not event_id:
        raise ValueError("classify-tags job requires event_id")

    track_ids: list[str] | None = ctx.params.get("track_ids")
    model: str = ctx.params.get("model") or "claude-sonnet-4-6"
    prompt_caching: bool = bool(ctx.params.get("prompt_caching", True))

    with ctx.db_session() as db:
        client = anthropic_client_for(db)

    with ctx.db_session() as db:
        q = select(EventTrack).where(EventTrack.event_id == event_id)
        if track_ids:
            q = q.where(EventTrack.spotify_id.in_(track_ids))
        rows = db.execute(q).scalars().all()

    total = len(rows)
    ctx.log(f"classify-tags: {total} tracks in chunks of {CHUNK_SIZE} (model={model}, caching={prompt_caching})")

    cum_in = cum_out = cum_cr = cum_cw = 0
    suggestions = 0
    tagged = 0
    done = 0

    for chunk_start in range(0, total, CHUNK_SIZE):
        if ctx.cancel_requested:
            break
        chunk = rows[chunk_start : chunk_start + CHUNK_SIZE]
        payload = [
            {
                "spotify_id": r.spotify_id,
                "name": r.name,
                "artists": list(r.artists),
                "bucket": r.bucket,
                "year": r.release_year,
                "bpm": r.bpm,
                "energy": r.audio_energy,
            }
            for r in chunk
        ]
        resp = await client.classify_tags(payload, model=model, prompt_caching=prompt_caching)
        cum_in += resp.input_tokens
        cum_out += resp.output_tokens
        cum_cr += resp.cache_read_tokens
        cum_cw += resp.cache_write_tokens
        ctx.cost(
            input_tokens=cum_in,
            output_tokens=cum_out,
            cache_read=cum_cr,
            cache_write=cum_cw,
            est_usd=resp.est_usd(),
        )

        with ctx.db_session() as db:
            by_id = {r.spotify_id: r for r in chunk}
            for tr in resp.results:
                row = by_id.get(tr.spotify_id)
                if row is None:
                    continue
                # Re-fetch attached row from this session
                row = db.get(EventTrack, row.id)
                if row is None:
                    continue
                row.energy = tr.energy
                row.function = list(tr.function)
                row.crowd = list(tr.crowd)
                row.mood_tags = list(tr.mood)
                if tr.genre_suggestion and tr.genre_suggestion != row.bucket:
                    row.llm_genre_suggestion = tr.genre_suggestion
                    row.llm_genre_suggestion_status = "pending"
                    suggestions += 1
                tagged += 1
                done += 1
                ctx.progress(done, total, item={"track_id": tr.spotify_id})
                ctx.save_checkpoint(tr.spotify_id, {"tagged": True})

    # Mark existing builds stale
    with ctx.db_session() as db:
        db.execute(update(EventBuild).where(EventBuild.event_id == event_id).values(is_stale=True))
        # Also write the data/<slug>.tags.json artifact for CLI compatibility
        from cratekeeper_api.orm import Event as _Event
        ev = db.get(_Event, event_id)
        if ev:
            tags_path = get_settings().data_dir / f"{ev.slug}.tags.json"
            with ctx.db_session() as db2:
                tracks = db2.execute(select(EventTrack).where(EventTrack.event_id == event_id)).scalars().all()
                payload = {
                    t.spotify_id: {
                        "energy": t.energy,
                        "function": list(t.function),
                        "crowd": list(t.crowd),
                        "mood": list(t.mood_tags),
                        "genre_suggestion": t.llm_genre_suggestion,
                    }
                    for t in tracks
                    if t.energy is not None
                }
            tags_path.parent.mkdir(parents=True, exist_ok=True)
            tags_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
            ctx.log(f"wrote tags artifact: {tags_path}")

    cache_hit_ratio = (cum_cr / max(1, cum_in + cum_cr))
    return {
        "tagged": tagged,
        "input_tokens": cum_in,
        "output_tokens": cum_out,
        "cache_read_tokens": cum_cr,
        "cache_write_tokens": cum_cw,
        "cache_hit_ratio": round(cache_hit_ratio, 4),
        "est_usd": round((cum_in * 3 + cum_out * 15 + cum_cr * 0.30) / 1_000_000, 4),
        "genre_suggestions": suggestions,
    }
