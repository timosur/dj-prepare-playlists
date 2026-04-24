# Cratekeeper — Architecture

**Last updated:** 2026-04-24

## 1. System Overview

Cratekeeper is a single-operator, local-first system. All components run on the DJ's Mac except Postgres (in Docker). Two front doors share one engine and one database:

- **CLI** (`crate`) — Python entry point; used directly and by the Copilot `prepare-event` skill.
- **Web app** — FastAPI backend + React/Vite/TS frontend on `localhost`.

```
                 ┌──────────────────────────┐
                 │  Operator (browser/CLI)  │
                 └────────────┬─────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ cratekeeper- │      │ cratekeeper- │      │ cratekeeper- │
│   web (SPA)  │─SSE─▶│   api (FastAPI)      │   cli (crate)│
│ Vite/React/TS│ HTTP │ + asyncio jobs│      │ Click + uv   │
└──────────────┘      └──────┬───────┘      └──────┬───────┘
                             │                     │
                             ├──────── shares ─────┤
                             ▼                     ▼
                      ┌────────────────────────────────┐
                      │ cratekeeper-cli/cratekeeper/*  │
                      │   (domain engine — Python)     │
                      │  classifier · matcher ·        │
                      │  mood_analyzer · tag_writer ·  │
                      │  event_builder · spotify/tidal │
                      └─────────────┬──────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
       ┌────────────┐       ┌────────────────┐    ┌──────────────┐
       │ PostgreSQL │       │  Local NAS     │    │ External APIs│
       │  (Docker)  │       │ /Volumes/Music │    │ Spotify/Tidal│
       │  + Alembic │       │  ~/.cratekeeper│    │ MusicBrainz  │
       └────────────┘       └────────────────┘    │ Anthropic    │
                                                  └──────────────┘
```

Postgres is the **single source of truth** shared by the CLI and the API. Both the CLI's `local_scanner` and the API write to the same `tracks` table; the API extends the schema (events, jobs, checkpoints, audit, settings, tag_backups) via Alembic.

## 2. Components

### 2.1 `cratekeeper-cli/` — Domain Engine + CLI

Python package built with `uv`/`pip`. Provides the `crate` CLI and is the canonical home for domain logic — both the CLI commands and the FastAPI handlers import these modules.

Key modules ([cratekeeper-cli/cratekeeper](../cratekeeper-cli/cratekeeper/)):

| Module | Responsibility |
|--------|----------------|
| `cli.py` | Click commands; thin shells over the domain modules. |
| `models.py` | `Track`, `EventPlan` data models — canonical shape for JSON artifacts. |
| `genre_buckets.py` | 18 genre bucket definitions (DB-backed override in API). |
| `classifier.py` | Rule-based bucket assignment. |
| `mood_analyzer.py` | Essentia + TF audio analysis (Apple Silicon native). |
| `mood_config.py` | Genre-specific mood thresholds (DB-backed override in API). |
| `matcher.py` | ISRC → exact → fuzzy local-library matching with `progress_callback`. |
| `tag_writer.py` | In-place ID3/Vorbis/MP4 writes; produces backup material. |
| `event_builder.py` | Copy/symlink into `Genre/Artist - Title.ext`. |
| `library_builder.py` | Master library accumulator. |
| `local_scanner.py` | NAS indexer; **owns** the `tracks` Postgres schema. |
| `spotify_client.py` / `tidal_client.py` | Direct REST clients (used by API too). |
| `musicbrainz_client.py` | Rate-limited (1 req/s) MusicBrainz client. |

### 2.2 `cratekeeper-api/` — FastAPI Backend

[cratekeeper-api/cratekeeper_api](../cratekeeper-api/cratekeeper_api/) — FastAPI app with an in-process asyncio job engine and SSE.

```
cratekeeper_api/
├── main.py            # FastAPI app, lifespan, middleware
├── config.py          # env-driven settings
├── container.py       # DI wiring (db, registries, services)
├── db.py / orm.py     # SQLAlchemy session + ORM models
├── schemas.py         # Pydantic request/response shapes
├── secrets_store.py   # Fernet-encrypted secrets
├── security.py        # bearer-token auth
├── seed.py            # initial settings/genre buckets seed
├── routers/
│   ├── events.py      # event CRUD + step submission
│   ├── jobs.py        # job list/get/cancel/resume + SSE stream
│   ├── library.py     # /library/stats, /events/{id}/builds, /sync-runs
│   ├── settings.py    # integrations, fs-roots, genre buckets, auth re-link
│   ├── audit.py       # /audit query
│   └── health.py
├── services/
│   ├── audit.py       # single funnel for audit log writes
│   ├── quality.py     # pre-flight Quality Checks
│   └── slug.py        # event slug generation
├── jobs/
│   ├── engine.py      # asyncio queue + semaphores (1 heavy / 4 light)
│   ├── registry.py    # handler registration
│   ├── context.py     # per-job context (db session, checkpoint API, SSE emit)
│   ├── dependencies.py# inter-step prerequisites
│   ├── rate_limit.py  # MusicBrainz pacing
│   ├── sse.py         # SSE hub with last-event-id replay
│   └── handlers/      # one module per pipeline step
├── integrations/      # Spotify/Tidal/Anthropic adapters (live + mock)
└── alembic/           # migrations (extend, don't duplicate, the CLI's tracks table)
```

**Job engine model:**

- One asyncio queue per process; jobs classified `heavy` (mood/tag/build) or `light` (everything else).
- Semaphores: 1 heavy concurrent, 4 light concurrent.
- Each job runs inside a `JobContext` that owns its DB session, checkpoint helpers, and SSE emitter.
- Handlers are pure functions of the context — easy to test, easy to swap for mocks.

**SSE channel:** one stream per job; clients subscribe with `Last-Event-ID` to replay missed messages on reconnect.

**Crash recovery:** per-unit checkpoints in Postgres (per-track for `analyze-mood`, per-batch for `classify-tags`, per-file for `apply-tags`/`build-*`). Resume jumps to the first unprocessed unit.

**Adapters:** `integrations/` holds live and mock implementations of Spotify, Tidal, Anthropic, and MusicBrainz. `CRATEKEEPER_TEST_MODE=true` swaps to mocks at container build time.

### 2.3 `cratekeeper-web/` — React Frontend

[cratekeeper-web/src](../cratekeeper-web/src/) — Vite + React 18 + TypeScript + Tailwind + TanStack Router/Query.

Top-level views:

| Route | Component | Purpose |
|-------|-----------|---------|
| `/` | [Dashboard.tsx](../cratekeeper-web/src/Dashboard.tsx) | Card grid of active events. |
| `/events/$id` | [EventDetail.tsx](../cratekeeper-web/src/EventDetail.tsx) | 12-step rail + per-step panels (Analyze, Match, Review, Sync, Build…). |
| `/library` | [MasterLibrary.tsx](../cratekeeper-web/src/MasterLibrary.tsx) | Global library stats. |
| `/audit` | [AuditLog.tsx](../cratekeeper-web/src/AuditLog.tsx) | Filterable audit timeline. |
| `/settings` | [Settings.tsx](../cratekeeper-web/src/Settings.tsx) | Auth, fs-roots, Anthropic, genre bucket editor. |

**Data:** all server state via TanStack Query against the FastAPI bearer-protected endpoints. Live job updates via SSE ([sse.ts](../cratekeeper-web/src/sse.ts)) feeding into the same query cache.

**Design:** dark, Spotify-adjacent. Full system in [DESIGN.md](../DESIGN.md).

### 2.4 Postgres (Docker)

`postgres:16-alpine` defined in [docker-compose.yml](../docker-compose.yml). Single database `djlib`. Schema authority: the CLI owns `tracks`; the API extends with `events`, `event_tracks`, `jobs`, `checkpoints`, `settings`, `audit_log`, `tag_backups`, `playlist_sync_runs`, etc.

### 2.5 MCP Servers (CLI Workflow Only)

`spotify-mcp/` (TypeScript) and `tidal-mcp/` (Python) implement Model Context Protocol servers used by the Copilot `prepare-event` skill. **They are not used by the web app** — the API talks to Spotify and Tidal directly via Python clients in `cratekeeper-cli/cratekeeper/`. Their config files (`spotify-config.json`, `tidal-session.json`) are read by the API as a credential source for first-run auth.

## 3. Key Data Flows

### 3.1 End-to-end pipeline (web app)

1. User creates an event → POST `/events` → row in `events`.
2. User submits step (e.g. `fetch`) → POST `/events/{id}/jobs` with handler name and params → row in `jobs` with status `queued`.
3. Job engine pops from queue, acquires the right semaphore, runs the handler in a worker task.
4. Handler emits SSE messages through `JobContext.sse(...)`; checkpoints written per unit.
5. On completion: status `succeeded`, results materialised in Postgres and on disk; audit row written.
6. Frontend's TanStack Query is invalidated by SSE; UI re-renders.

### 3.2 Tag write + undo

1. `apply-tags` reads `data/<slug>.tags.json` (same shape the CLI produces), backs up each file's bytes to `~/.cratekeeper/tag-backups/<event_id>/<spotify_id>.<ext>`, writes the new tags, records a `tag_backups` row per file.
2. Downstream `build-event` and `build-library` rows for this event are marked stale.
3. `undo-tags` reads the backup rows, restores files, consumes the rows on success.

### 3.3 SSE & Resume

- Each running job emits `progress`, `log`, and `metric` events on its SSE channel.
- The SSE hub keeps a bounded ring buffer per job; clients reconnect with `Last-Event-ID` to replay.
- On process restart, jobs in `running` status are eligible for **resume from checkpoint** triggered by the user from the UI.

## 4. Storage Layout

| Path | Purpose |
|------|---------|
| `data/*.json` | Event artifacts: raw fetch, `.classified.json`, `.tags.json`, missing-track reports. |
| `~/Music/Library/Genre/…` | Master library (accumulated across events). |
| `~/Music/Events/<event>/Genre/…` | Per-event folder build (copy or symlink). |
| `~/.cratekeeper/tag-backups/<event_id>/` | Byte-level audio file backups for undo. |
| `/Volumes/Music` (or NAS mount) | Source library — read-only. |
| Postgres `djlib` | All structured state. |

## 5. Security Model

- **Auth:** bearer token (`CRATEKEEPER_API_TOKEN`) on every API call. Token is configured in Settings UI and stored in `localStorage` on the frontend.
- **CORS:** restricted to `http://localhost` and `http://localhost:5173`.
- **Secrets at rest:** Spotify/Tidal/Anthropic credentials encrypted with `CRATEKEEPER_FERNET_KEY` in the `settings` table.
- **Filesystem roots:** every FS-touching handler validates the requested path against an allow-list of configured roots (NAS mount, library root, event-output root).
- **Audit:** every mutation goes through `services/audit.record(...)`. There is no direct `audit_log` insert outside that service.
- **Localhost-only:** no public ingress; the system is not designed for external exposure.

## 6. Concurrency & Reliability

| Concern | Mechanism |
|---------|-----------|
| CPU/IO contention | Asyncio semaphores: 1 heavy + 4 light. |
| Long-running jobs | Per-unit checkpoints in Postgres → resumable. |
| External rate limits | `jobs/rate_limit.py` (MusicBrainz 1 req/s); adapter back-off for Spotify/Tidal. |
| Destructive ops | `dry_run` flag for `apply-tags`, `build-event`, `build-library`. |
| Tag write reversibility | Per-file byte snapshots + `undo-tags` job. |
| Stale derivative artifacts | `apply-tags` marks downstream builds stale; UI banners until rebuild. |
| Crash mid-job | Job moves to `failed`/`cancelled`; user-initiated resume from last checkpoint. |
| CLI/Web drift | Single Postgres schema; both write through the same domain modules. |

## 7. Deployment

[docker-compose.yml](../docker-compose.yml) defines four services:

| Service | Image / Build | Port |
|---------|---------------|------|
| `db` | `postgres:16-alpine` | 5432 |
| `crate` | `./cratekeeper-cli` (CLI container, optional) | — |
| `api` | `./cratekeeper-api` | 8765 |
| `web` | `./cratekeeper-web` (nginx serving Vite build) | 8080 |

Volume mounts give the API access to the NAS (`/Volumes/Music` → `/music:ro`), the master library (`~/Music/Library` → `/library`), and the user's `~/.cratekeeper/` for backups and persisted credentials.

For development, Postgres runs in Docker while the API and the frontend run natively (`uv run` and `npm run dev`).

## 8. Testing

- **Backend:** `uv run pytest -q` — uses an ephemeral Docker Postgres; mocks Spotify/Tidal/Anthropic via `CRATEKEEPER_TEST_MODE=true`. Coverage spans events, jobs, SSE, dependencies, hardening (audit, dry-run, undo).
- **Frontend:** `npm run build` (zero TS errors gate) plus Playwright smoke and pipeline specs in [cratekeeper-web/e2e/](../cratekeeper-web/e2e/).
- **CLI:** exercised end-to-end via the `prepare-event` skill against `data/wedding-test.json` fixtures.

## 9. Known Gaps

- True interactive OAuth flows for Spotify/Tidal — current re-link endpoints validate file-based credentials only.
- Drag-and-drop reorder for genre buckets.
- Apple Silicon mood-analysis acceptance run inside the `api` container has not been exercised in CI.
- Cross-event Spotify/Tidal master playlist management is deferred past v1.

## 10. References

- [README.md](../README.md) — install + CLI walkthrough.
- [PRD.md](PRD.md) — product requirements.
- [DESIGN.md](../DESIGN.md) — visual design system.
- [plans/ui/01-foundations.md](../plans/ui/01-foundations.md) — architecture, data model, API contract decisions.
- [plans/ui/02-backend.md](../plans/ui/02-backend.md) — backend implementation plan.
- [plans/ui/03-frontend.md](../plans/ui/03-frontend.md) — frontend implementation plan.
- [plans/ui/04-hardening.md](../plans/ui/04-hardening.md) — reliability + safety.
- [plans/ui/STATUS.md](../plans/ui/STATUS.md) — shipped vs. planned.
