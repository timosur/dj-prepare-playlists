"""Pydantic API schemas — request/response shapes."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

JobType = Literal[
    "fetch",
    "enrich",
    "classify",
    "scan-incremental",
    "scan-full",
    "match",
    "analyze-mood",
    "classify-tags",
    "apply-tags",
    "undo-tags",
    "build-library",
    "build-event",
    "sync-spotify",
    "sync-tidal",
    "refetch",
]

JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
Confidence = Literal["high", "medium", "low"]
MatchStatus = Literal["isrc", "exact", "fuzzy", "missing"]


class EventCreate(BaseModel):
    name: str
    date: str | None = None
    source_playlist_url: str | None = None
    slug: str | None = None
    build_mode: Literal["copy", "symlink"] = "copy"


class EventUpdate(BaseModel):
    name: str | None = None
    date: str | None = None
    slug: str | None = None
    build_mode: Literal["copy", "symlink"] | None = None


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    date: str | None
    source_playlist_url: str | None
    source_playlist_id: str | None
    source_playlist_name: str | None
    build_mode: str
    created_at: datetime
    updated_at: datetime
    track_count: int = 0


class EventTrackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_id: str
    spotify_id: str
    name: str
    artists: list[str]
    album: str | None
    duration_ms: int
    isrc: str | None
    release_year: int | None
    artist_genres: list[str]
    bucket: str | None
    confidence: Confidence | None
    era: str | None
    local_path: str | None
    match_status: MatchStatus | None
    acquire_later: bool
    bpm: float | None
    key: str | None
    energy: str | None
    function: list[str]
    crowd: list[str]
    mood_tags: list[str]
    llm_genre_suggestion: str | None
    llm_genre_suggestion_status: str | None


class EventTrackPatch(BaseModel):
    bucket: str | None = None
    confidence: Confidence | None = None
    acquire_later: bool | None = None
    llm_genre_suggestion_status: Literal["pending", "accepted", "ignored"] | None = None
    energy: str | None = None
    function: list[str] | None = None
    crowd: list[str] | None = None
    mood_tags: list[str] | None = None


class TrackBulkAction(BaseModel):
    track_ids: list[str]
    action: Literal["rebucket", "set_acquire_later", "accept_genre_suggestion", "ignore_genre_suggestion"]
    bucket: str | None = None  # for "rebucket"
    acquire_later: bool | None = None  # for "set_acquire_later"


class JobEnqueue(BaseModel):
    type: JobType
    params: dict[str, Any] = Field(default_factory=dict)


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_id: str | None
    type: str
    status: JobStatus
    params: dict[str, Any]
    summary: dict[str, Any]
    error: dict[str, Any] | None
    progress_i: int
    progress_total: int
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime


class MountStatus(BaseModel):
    root: str
    exists: bool
    readable: bool


class MountReport(BaseModel):
    ok: bool
    roots: list[MountStatus]


class QualityCheck(BaseModel):
    name: str
    status: Literal["pass", "warn", "fail"]
    detail: str | None = None
    metric: float | int | None = None


class QualityReport(BaseModel):
    overall: Literal["pass", "warn", "fail"]
    checks: list[QualityCheck]


class GenreBucketIn(BaseModel):
    name: str
    genre_tags: list[str]
    is_fallback: bool = False


class GenreBucketOut(GenreBucketIn):
    id: int
    sort_order: int


class GenreBucketsReplace(BaseModel):
    buckets: list[GenreBucketIn]  # order is meaningful — first match wins


class AnthropicSettingsIn(BaseModel):
    api_key: str | None = None
    model: str | None = "claude-sonnet-4-6"
    prompt_caching: bool = True


class AnthropicSettingsOut(BaseModel):
    configured: bool
    model: str
    prompt_caching: bool


class FsRootsIn(BaseModel):
    roots: list[str]


class FsRootsOut(BaseModel):
    roots: list[str]


class TagVocabularies(BaseModel):
    energy: list[str]
    function: list[str]
    crowd: list[str]
    mood: list[str]


class ProblemDetails(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    code: str | None = None
