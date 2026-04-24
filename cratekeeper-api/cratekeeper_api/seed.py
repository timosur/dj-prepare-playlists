"""Seed default genre buckets + tag vocabularies into DB on first boot.

Idempotent: safe to call repeatedly; only inserts if rows are missing.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from cratekeeper.genre_buckets import DEFAULT_BUCKETS
from cratekeeper_api.orm import GenreBucketRow, Setting

# Fixed v1 vocabularies (per plan: not user-editable).
TAG_VOCABULARIES = {
    "energy": ["low", "mid", "high"],
    "function": ["floorfiller", "singalong", "bridge", "reset", "closer", "opener"],
    "crowd": ["mixed-age", "older", "younger", "family"],
    "mood": ["feelgood", "emotional", "euphoric", "nostalgic"],
}


def seed_genre_buckets(db: Session) -> None:
    existing = db.execute(select(GenreBucketRow.name)).scalars().all()
    if existing:
        return
    for i, b in enumerate(DEFAULT_BUCKETS):
        db.add(GenreBucketRow(name=b.name, genre_tags=list(b.genre_tags), sort_order=i, is_fallback=False))


def seed_tag_vocabularies(db: Session) -> None:
    if db.get(Setting, "tag_vocabularies"):
        return
    import json
    db.add(Setting(key="tag_vocabularies", value=json.dumps(TAG_VOCABULARIES), is_secret=False))


def seed_all(db: Session) -> None:
    seed_genre_buckets(db)
    seed_tag_vocabularies(db)
