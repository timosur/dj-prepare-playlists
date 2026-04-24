"""Initial schema — all backend-owned tables.

Coexistence: the existing `tracks` table (owned by cratekeeper-cli/local_scanner.py)
is created with `CREATE TABLE IF NOT EXISTS` here so a fresh install also works
without first running the CLI scanner. The columns mirror local_scanner._get_conn
exactly.

Revision ID: 0001_initial
Revises:
Create Date: 2025-04-24
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Existing `tracks` table: idempotent create to match local_scanner.py ---
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS tracks (
            path TEXT PRIMARY KEY,
            rel_path TEXT,
            title TEXT,
            artist TEXT,
            album TEXT,
            isrc TEXT,
            year INTEGER,
            duration_ms INTEGER,
            format TEXT,
            title_norm TEXT,
            artist_norm TEXT
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_rel_path ON tracks(rel_path) WHERE rel_path IS NOT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_isrc ON tracks(isrc) WHERE isrc IS NOT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_artist_title ON tracks(artist_norm, title_norm)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS scan_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )

    # --- events ------------------------------------------------------------
    op.create_table(
        "events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("slug", sa.Text, nullable=False, unique=True),
        sa.Column("date", sa.String(10)),
        sa.Column("source_playlist_url", sa.Text),
        sa.Column("source_playlist_id", sa.Text),
        sa.Column("source_playlist_name", sa.Text),
        sa.Column("build_mode", sa.String(16), nullable=False, server_default="copy"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- event_tracks -------------------------------------------------------
    op.create_table(
        "event_tracks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("spotify_id", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("artists", JSONB, nullable=False, server_default="[]"),
        sa.Column("artist_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("album", sa.Text),
        sa.Column("duration_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("isrc", sa.Text),
        sa.Column("release_year", sa.Integer),
        sa.Column("artist_genres", JSONB, nullable=False, server_default="[]"),
        sa.Column("bucket", sa.Text),
        sa.Column("confidence", sa.String(8)),
        sa.Column("era", sa.String(16)),
        sa.Column("local_path", sa.Text),
        sa.Column("match_status", sa.String(16)),
        sa.Column("acquire_later", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("bpm", sa.Float),
        sa.Column("key", sa.String(16)),
        sa.Column("danceability", sa.Float),
        sa.Column("audio_energy", sa.Float),
        sa.Column("audio_mood", JSONB, nullable=False, server_default="{}"),
        sa.Column("arousal", sa.Float),
        sa.Column("valence", sa.Float),
        sa.Column("energy", sa.String(8)),
        sa.Column("function", JSONB, nullable=False, server_default="[]"),
        sa.Column("crowd", JSONB, nullable=False, server_default="[]"),
        sa.Column("mood_tags", JSONB, nullable=False, server_default="[]"),
        sa.Column("llm_genre_suggestion", sa.Text),
        sa.Column("llm_genre_suggestion_status", sa.String(16)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("event_id", "spotify_id", name="uq_event_tracks_event_spotify"),
    )
    op.create_index("ix_event_tracks_event_id", "event_tracks", ["event_id"])
    op.create_index("ix_event_tracks_isrc", "event_tracks", ["isrc"])

    # --- event_builds -------------------------------------------------------
    op.create_table(
        "event_builds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("path", sa.Text, nullable=False),
        sa.Column("is_stale", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("last_built_at", sa.DateTime(timezone=True)),
        sa.Column("summary", JSONB, nullable=False, server_default="{}"),
    )
    op.create_index("ix_event_builds_event_id", "event_builds", ["event_id"])

    # --- event_fetches ------------------------------------------------------
    op.create_table(
        "event_fetches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("added", JSONB, nullable=False, server_default="[]"),
        sa.Column("removed", JSONB, nullable=False, server_default="[]"),
        sa.Column("unchanged", JSONB, nullable=False, server_default="[]"),
        sa.Column("job_id", sa.String(36)),
    )
    op.create_index("ix_event_fetches_event_id", "event_fetches", ["event_id"])

    # --- job_runs -----------------------------------------------------------
    op.create_table(
        "job_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id", ondelete="CASCADE")),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("params", JSONB, nullable=False, server_default="{}"),
        sa.Column("summary", JSONB, nullable=False, server_default="{}"),
        sa.Column("error", JSONB),
        sa.Column("progress_i", sa.Integer, nullable=False, server_default="0"),
        sa.Column("progress_total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_job_runs_event_id", "job_runs", ["event_id"])
    op.create_index("ix_job_runs_type", "job_runs", ["type"])
    op.create_index("ix_job_runs_status", "job_runs", ["status"])

    # --- job_checkpoints ----------------------------------------------------
    op.create_table(
        "job_checkpoints",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("job_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.Text, nullable=False),
        sa.Column("payload", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("job_id", "key", name="uq_checkpoint_job_key"),
    )
    op.create_index("ix_job_checkpoints_job_id", "job_checkpoints", ["job_id"])

    # --- playlist_sync_runs -------------------------------------------------
    op.create_table(
        "playlist_sync_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(16), nullable=False),
        sa.Column("job_id", sa.String(36)),
        sa.Column("summary", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_playlist_sync_runs_event_id", "playlist_sync_runs", ["event_id"])

    # --- settings -----------------------------------------------------------
    op.create_table(
        "settings",
        sa.Column("key", sa.Text, primary_key=True),
        sa.Column("value", sa.Text),
        sa.Column("is_secret", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- genre_buckets ------------------------------------------------------
    op.create_table(
        "genre_buckets",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text, nullable=False, unique=True),
        sa.Column("genre_tags", JSONB, nullable=False, server_default="[]"),
        sa.Column("sort_order", sa.Integer, nullable=False),
        sa.Column("is_fallback", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_genre_buckets_sort_order", "genre_buckets", ["sort_order"])

    # --- mood_thresholds ----------------------------------------------------
    op.create_table(
        "mood_thresholds",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("bucket_name", sa.Text, nullable=False, unique=True),
        sa.Column("config", JSONB, nullable=False, server_default="{}"),
    )

    # --- audit_log ----------------------------------------------------------
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("actor", sa.String(64), nullable=False, server_default="local"),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_kind", sa.String(32)),
        sa.Column("target_id", sa.String(64)),
        sa.Column("payload", JSONB, nullable=False, server_default="{}"),
    )
    op.create_index("ix_audit_log_ts", "audit_log", ["ts"])


def downgrade() -> None:
    for tbl in [
        "audit_log",
        "mood_thresholds",
        "genre_buckets",
        "settings",
        "playlist_sync_runs",
        "job_checkpoints",
        "job_runs",
        "event_fetches",
        "event_builds",
        "event_tracks",
        "events",
    ]:
        op.drop_table(tbl)
    # Intentionally leave `tracks` and `scan_meta` (owned by cratekeeper-cli).
