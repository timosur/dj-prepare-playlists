"""`classify` job — applies the rule-based genre classifier from cratekeeper-cli
against `event_tracks` rows. DB-backed buckets are loaded from `genre_buckets`
(seeded from the CLI defaults).
"""

from __future__ import annotations

from sqlalchemy import select

from cratekeeper.classifier import classify_track
from cratekeeper.genre_buckets import FALLBACK_BUCKET, GenreBucket
from cratekeeper.models import Track
from cratekeeper_api.jobs.context import JobContext
from cratekeeper_api.jobs.registry import register
from cratekeeper_api.orm import EventTrack, GenreBucketRow


def _load_buckets(db) -> list[GenreBucket]:
    rows = db.execute(select(GenreBucketRow).order_by(GenreBucketRow.sort_order)).scalars().all()
    return [GenreBucket(name=r.name, genre_tags=list(r.genre_tags)) for r in rows]


def _to_cli_track(et: EventTrack) -> Track:
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


@register("classify")
async def run(ctx: JobContext) -> dict:
    event_id = ctx.event_id
    if not event_id:
        raise ValueError("classify job requires event_id")

    track_ids: list[str] | None = ctx.params.get("track_ids")
    min_bucket_size: int = int(ctx.params.get("min_bucket_size", 3))

    with ctx.db_session() as db:
        buckets = _load_buckets(db)
        q = select(EventTrack).where(EventTrack.event_id == event_id)
        if track_ids:
            q = q.where(EventTrack.spotify_id.in_(track_ids))
        rows = db.execute(q).scalars().all()
        total = len(rows)
        ctx.log(f"classifying {total} tracks against {len(buckets)} buckets")

        bucket_counts: dict[str, int] = {}
        low_conf = 0
        for i, et in enumerate(rows, 1):
            bucket_name, confidence = classify_track(_to_cli_track(et), buckets)
            et.bucket = bucket_name
            et.confidence = confidence
            t_for_era = _to_cli_track(et)
            et.era = t_for_era.compute_era()
            bucket_counts[bucket_name] = bucket_counts.get(bucket_name, 0) + 1
            if confidence == "low":
                low_conf += 1
            ctx.progress(i, total, item={"track_id": et.spotify_id})
            ctx.save_checkpoint(et.spotify_id, {"bucket": bucket_name})

        # Consolidate small buckets → fallback
        small = {b for b, n in bucket_counts.items() if n < min_bucket_size and b != FALLBACK_BUCKET}
        if small:
            ctx.log(f"merging {len(small)} small buckets into '{FALLBACK_BUCKET}'", level="info")
            for et in rows:
                if et.bucket in small:
                    et.bucket = FALLBACK_BUCKET
                    et.confidence = "low"
            # Recount
            final_counts: dict[str, int] = {}
            for et in rows:
                final_counts[et.bucket or FALLBACK_BUCKET] = final_counts.get(et.bucket or FALLBACK_BUCKET, 0) + 1
            bucket_counts = final_counts

    return {
        "bucket_counts": bucket_counts,
        "low_confidence": low_conf,
        "fallback": bucket_counts.get(FALLBACK_BUCKET, 0),
        "total": total,
    }
