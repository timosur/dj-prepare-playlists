# Cratekeeper API

FastAPI backend that orchestrates the existing `cratekeeper-cli` pipeline.

This is the M1 + M2-baseline output of the [UI plan](../plans/ui/README.md).
See [plans/ui/artifacts/](../plans/ui/artifacts/) for architecture, security,
API contract, and SSE event schemas.

## What's implemented

- **M1 design artifacts** — architecture, security, API contract, SSE schemas.
- **Schema** — Alembic + initial migration for all backend-owned tables (`events`, `event_tracks`, `event_builds`, `event_fetches`, `job_runs`, `job_checkpoints`, `playlist_sync_runs`, `settings`, `genre_buckets`, `mood_thresholds`, `audit_log`). The existing `tracks` table is created idempotently to match `cratekeeper-cli/local_scanner.py`.
- **Async job engine** — in-process asyncio runner with global heavy-job semaphore, per-type light semaphores, DB-backed checkpoints, two SSE channels per job (progress + log) plus a per-event fan-out channel.
- **Job handlers** wired end-to-end: `fetch`, `classify`, `classify-tags`, `refetch`. Other types (`enrich`, `scan-*`, `match`, `analyze-mood`, `apply-tags`, `build-*`, `sync-*`) have their registry slot ready and follow the same pattern.
- **Integration adapters** — Spotify, Tidal, MusicBrainz, Anthropic. All four currently default to in-process **mocks** (per the user's "mock now, real creds later" decision). Real clients are M2 step 3 work.
- **REST API** — events CRUD, event tracks (filter + bulk actions), quality checks, jobs (enqueue/list/cancel/resume), SSE streams, settings (anthropic, fs-roots, genre buckets, tag vocabularies).
- **Security primitives** — Fernet-encrypted secrets, FS-root path safety, mount pre-flight, bearer-token auth (test-mode bypass).
- **Pytest harness** — testcontainers Postgres, Alembic migrations applied per session, table truncation between tests, isolated config dir per session. Covers: health, events CRUD, vertical pipeline (fetch → classify → classify-tags → quality), bulk actions, refetch diff, async engine semaphore + checkpoints + failure handling, SSE replay + live delivery, settings.

## Run locally

Postgres must be up (existing `docker-compose.yml`).

```bash
cd cratekeeper-api
uv sync --all-extras    # or: pip install -e ".[test]"
alembic upgrade head
cratekeeper-api         # binds 127.0.0.1:8765
```

## Test

```bash
cd cratekeeper-api
uv run pytest -q
```

Tests start an ephemeral Postgres container via testcontainers; Docker must be running.

## What's NOT implemented yet (intentional, by milestone)

- Real Spotify/Tidal/Anthropic/MusicBrainz network clients (mocks only).
- OAuth callback endpoints (`/oauth/spotify/...`, `/oauth/tidal/...`).
- Heavy job handlers — `scan-*`, `match`, `analyze-mood`, `apply-tags`, `build-library`, `build-event`, `sync-*`. Skeletons can copy the `fetch`/`classify` pattern.
- Tag-write backup + undo (M4).
- Audit log writes for destructive ops (M4 — table exists, writers don't).
- Frontend (M3).
- LLM tag classifier writing the real Anthropic API (mock returns deterministic tags + fake token counts).

Each remaining handler slots into `cratekeeper_api/jobs/handlers/`, registers via `@register("type", heavy=...)`, and reuses the existing `JobContext` for SSE/checkpoints. The integration adapter pattern (`Protocol` + `MockX` + `get_X_adapter`) is set up to make the real clients drop-in replacements.
