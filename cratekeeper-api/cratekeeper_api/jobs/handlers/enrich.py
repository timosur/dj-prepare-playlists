"""`enrich` job — fill missing artist genres / release year via MusicBrainz.

Targets event tracks that have an ISRC but are missing either ``artist_genres``
or ``release_year``. Uses the configured ``MusicBrainzAdapter`` (the live one
enforces ~1 req/sec). Mirrors the CLI ``crate enrich`` step that runs between
``fetch`` and ``classify`` per the prepare-event skill.
"""

from __future__ import annotations

from sqlalchemy import select

from cratekeeper.models import Track
from cratekeeper_api.container import get_container
from cratekeeper_api.jobs.context import JobContext
from cratekeeper_api.jobs.registry import register
from cratekeeper_api.orm import EventTrack


@register("enrich")
async def run(ctx: JobContext) -> dict:
    event_id = ctx.event_id
    if not event_id:
        raise ValueError("enrich job requires event_id")

    mb = get_container().musicbrainz

    with ctx.db_session() as db:
        rows = db.execute(select(EventTrack).where(EventTrack.event_id == event_id)).scalars().all()
        candidates = [
            r for r in rows
            if r.isrc and (not r.artist_genres or not r.release_year)
        ]
        candidate_ids = [r.spotify_id for r in candidates]

    total_candidates = len(candidate_ids)
    ctx.log(f"enriching {total_candidates} of {len(rows)} tracks via MusicBrainz")

    enriched = 0
    genres_added = 0
    years_added = 0

    for i, sp_id in enumerate(candidate_ids, 1):
        with ctx.db_session() as db:
            et = db.execute(
                select(EventTrack).where(
                    EventTrack.event_id == event_id,
                    EventTrack.spotify_id == sp_id,
                )
            ).scalar_one_or_none()
            if et is None or not et.isrc:
                ctx.progress(i, total_candidates)
                continue

            isrc = et.isrc
            display = f'"{et.name}" by {", ".join(et.artists)}'

        # Network call outside the DB session to avoid holding a connection.
        genres, year = await mb.lookup_by_isrc(isrc)

        with ctx.db_session() as db:
            et = db.execute(
                select(EventTrack).where(
                    EventTrack.event_id == event_id,
                    EventTrack.spotify_id == sp_id,
                )
            ).scalar_one_or_none()
            if et is None:
                ctx.progress(i, total_candidates)
                continue

            updated = False
            if genres and not et.artist_genres:
                et.artist_genres = list(genres)
                genres_added += 1
                updated = True
            if year and not et.release_year:
                et.release_year = year
                # Keep era in sync if other code derives it from release_year.
                t = Track(
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
                et.era = t.compute_era()
                years_added += 1
                updated = True
            if updated:
                enriched += 1
                ctx.save_checkpoint(
                    et.spotify_id,
                    {"genres": len(genres or []), "year": year},
                )

        ctx.progress(i, total_candidates, item={"track_id": sp_id, "display": display})

    return {
        "candidates": total_candidates,
        "enriched": enriched,
        "genres_added": genres_added,
        "release_years_added": years_added,
        "total": len(rows),
    }
