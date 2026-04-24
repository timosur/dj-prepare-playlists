"""SQLAlchemy ORM models for all backend-owned tables.

The pre-existing `tracks` table (owned by cratekeeper-cli/local_scanner.py) is
mapped read-only here as `LibraryTrack` so we never duplicate its DDL. New
tables defined below are additive and migrated by Alembic.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cratekeeper_api.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# --- Existing tracks table (mapped, NOT created by Alembic) -----------------


class LibraryTrack(Base):
    """Read/write mapping of the `tracks` table created by cratekeeper-cli's
    `local_scanner.py`. Alembic must NOT create or alter this table — coexistence
    contract: cratekeeper-cli owns the DDL.
    """

    __tablename__ = "tracks"
    __table_args__ = {"info": {"skip_autogenerate": True}}

    path: Mapped[str] = mapped_column(Text, primary_key=True)
    rel_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    artist: Mapped[str | None] = mapped_column(Text, nullable=True)
    album: Mapped[str | None] = mapped_column(Text, nullable=True)
    isrc: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    format: Mapped[str | None] = mapped_column(Text, nullable=True)
    title_norm: Mapped[str | None] = mapped_column(Text, nullable=True)
    artist_norm: Mapped[str | None] = mapped_column(Text, nullable=True)


# --- New backend-owned tables ------------------------------------------------


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # YYYY-MM-DD
    source_playlist_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_playlist_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_playlist_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    build_mode: Mapped[str] = mapped_column(String(16), default="copy")  # copy | symlink
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    tracks: Mapped[list[EventTrack]] = relationship(back_populates="event", cascade="all, delete-orphan")


class EventTrack(Base):
    __tablename__ = "event_tracks"
    __table_args__ = (UniqueConstraint("event_id", "spotify_id", name="uq_event_tracks_event_spotify"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id", ondelete="CASCADE"), index=True)
    spotify_id: Mapped[str] = mapped_column(Text, nullable=False)

    # Snapshot of Spotify metadata at fetch time
    name: Mapped[str] = mapped_column(Text, nullable=False)
    artists: Mapped[list[str]] = mapped_column(JSONB, default=list)
    artist_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    album: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    isrc: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    release_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    artist_genres: Mapped[list[str]] = mapped_column(JSONB, default=list)

    # Per-event classification + review state
    bucket: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(8), nullable=True)  # high|medium|low
    era: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Local match
    local_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    match_status: Mapped[str | None] = mapped_column(String(16), nullable=True)  # isrc|exact|fuzzy|missing
    acquire_later: Mapped[bool] = mapped_column(Boolean, default=False)

    # Audio analysis
    bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    key: Mapped[str | None] = mapped_column(String(16), nullable=True)
    danceability: Mapped[float | None] = mapped_column(Float, nullable=True)
    audio_energy: Mapped[float | None] = mapped_column(Float, nullable=True)
    audio_mood: Mapped[dict] = mapped_column(JSONB, default=dict)
    arousal: Mapped[float | None] = mapped_column(Float, nullable=True)
    valence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # LLM tags
    energy: Mapped[str | None] = mapped_column(String(8), nullable=True)
    function: Mapped[list[str]] = mapped_column(JSONB, default=list)
    crowd: Mapped[list[str]] = mapped_column(JSONB, default=list)
    mood_tags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    llm_genre_suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_genre_suggestion_status: Mapped[str | None] = mapped_column(String(16), nullable=True)  # pending|accepted|ignored

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    event: Mapped[Event] = relationship(back_populates="tracks")


class EventBuild(Base):
    __tablename__ = "event_builds"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # library | event-folder
    path: Mapped[str] = mapped_column(Text, nullable=False)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False)
    last_built_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[dict] = mapped_column(JSONB, default=dict)


class EventFetch(Base):
    __tablename__ = "event_fetches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id", ondelete="CASCADE"), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    added: Mapped[list[str]] = mapped_column(JSONB, default=list)
    removed: Mapped[list[str]] = mapped_column(JSONB, default=list)
    unchanged: Mapped[list[str]] = mapped_column(JSONB, default=list)
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    event_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("events.id", ondelete="CASCADE"), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)  # queued|running|succeeded|failed|cancelled
    params: Mapped[dict] = mapped_column(JSONB, default=dict)
    summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    error: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    progress_i: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class JobCheckpoint(Base):
    __tablename__ = "job_checkpoints"
    __table_args__ = (UniqueConstraint("job_id", "key", name="uq_checkpoint_job_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("job_runs.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(Text, nullable=False)  # e.g. spotify track id
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class PlaylistSyncRun(Base):
    __tablename__ = "playlist_sync_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)  # spotify | tidal
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)  # may be Fernet-encrypted
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class GenreBucketRow(Base):
    __tablename__ = "genre_buckets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    genre_tags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    is_fallback: Mapped[bool] = mapped_column(Boolean, default=False)


class MoodThreshold(Base):
    __tablename__ = "mood_thresholds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bucket_name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(64), default="local")
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
