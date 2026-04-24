# Implementation Status

This document tracks what's actually shipped versus the plan in this folder.

## ✅ Milestone 1 — Foundations

See [artifacts/](artifacts/) for the design notes.

## ✅ Milestone 2 — Backend

`cratekeeper-api/` — FastAPI app, Alembic migrations, in-process asyncio job
engine with semaphores (1 heavy / 4 light), SSE hub with last-event-id replay,
encrypted secrets store, postgres-backed
event/track/job/checkpoint/settings/audit tables.

**Job handlers wired (live + mock):**
- `fetch` — Spotify playlist intake
- `classify` — genre bucketing
- `classify-tags` — Anthropic Sonnet via official SDK (prompt caching)
- `refetch` — playlist diff + downstream re-run
- `scan-incremental` / `scan-full` — local library scanner (FS-root validated)
- `match` — ISRC / exact / fuzzy matching against local library
- `analyze-mood` — Essentia BPM/key/energy/mood with per-track checkpoints
- `apply-tags` — writes ID3/Vorbis/MP4 tags with file-level backups under
  `~/.cratekeeper/tag-backups/<event_id>/`; supports `dry_run`; marks
  downstream builds stale
- `undo-tags` — restores audio files from the tag-write snapshots; supports
  `dry_run`; consumes backup rows on success
- `build-event` — copies/symlinks to event folder (Genre/Artist - Title.ext);
  supports `dry_run` (diff-only, no FS writes)
- `build-library` — global library export, dedups across events; supports
  `dry_run`
- `sync-spotify` / `sync-tidal` — creates platform sub-playlists; persists
  `PlaylistSyncRun` with click-through URL

**Adapters:** Spotify (live via spotipy), Tidal (live via tidalapi),
Anthropic (live via `anthropic` SDK), MusicBrainz (live via CLI client) —
all with mock counterparts auto-selected when `CRATEKEEPER_TEST_MODE=true`.

**Endpoints beyond CRUD:** `/library/stats`, `/events/{id}/builds`,
`/events/{id}/sync-runs`, `/events/{id}/tidal-urls`,
`/settings/auth/{spotify,tidal}` + `/relink`, `/audit` (with
`target_kind`/`target_id` filters).

**Tests:** 22/22 green (`uv run pytest -q`) using ephemeral docker postgres.

## ✅ Milestone 3 — Frontend

`cratekeeper-web/` — Vite + React + TS + Tailwind + TanStack Query/Router.

**Implemented:**
- Dashboard (list/create events).
- Event detail page with the **full 12-step pipeline**: fetch / classify /
  classify-tags / scan-incremental / match / analyze-mood / apply-tags /
  undo-tags / build-event / build-library / sync-spotify / sync-tidal —
  each with inline param forms (including `dry_run` toggles for destructive
  steps), live SSE progress, cost telemetry, log viewer, cancel/retry, job
  history, quality summary, track table.
- **Review panel** — low-confidence-first list, bulk re-bucket / mark
  acquire-later, pending LLM-suggestion accept/ignore lane.
- **Match panel** — Tidal purchase URLs for unmatched ISRCs.
- **Analyze panel** — energy + BPM histograms.
- **Build panel** — build history with stale banner.
- **Sync panel** — playlist sync history with click-through links.
- **Master library** view (`/library`).
- **Audit log** view (`/audit`).
- Settings: integration health + in-app re-link buttons (Spotify/Tidal),
  Anthropic API key + model + prompt-caching toggle, fs-roots view,
  bearer-token entry, **genre bucket editor** (reorder / edit / fallback flag).

**Frontend build:** `npm run build` → 0 TypeScript errors.

## ✅ Milestone 4 — Hardening

**Reliability + safety:**
- **Audit log** — single-funnel `services/audit.record(...)` writing to
  `audit_log`. Wired into job submit/cancel/resume, `apply-tags`,
  `undo-tags`, `build-event`, `build-library`, `sync-spotify`,
  `sync-tidal`, and the settings PUTs (anthropic / fs-roots /
  genre-buckets). Surfaced via `GET /audit` and the `/audit` UI page.
- **Failure recovery** — resume-from-checkpoint already in M2; UI button
  visible on failed/cancelled jobs in EventDetail's job history.
- **Dry-run mode** — `apply-tags`, `build-event`, `build-library` accept
  `dry_run` and emit a diff-only summary without touching the FS. Surfaced
  as a checkbox in EventDetail step forms.
- **Tag-write undo** — per-track byte-level snapshots in
  `~/.cratekeeper/tag-backups/<event_id>/<spotify_id>.<ext>` recorded in a
  `tag_backups` table; `undo-tags` job restores them and consumes the
  backup rows.

**Verification:**
- 22/22 backend tests green. New `tests/test_hardening.py` covers audit
  recording, build-event dry-run leaves the FS untouched, and undo-tags
  smoke-runs against an empty backup set.
- Frontend `npm run build` → 0 errors.

**Rollout:**
- `docker-compose.yml` extended with `api` and `web` services
  ([cratekeeper-api/Dockerfile](../../cratekeeper-api/Dockerfile),
  [cratekeeper-web/Dockerfile](../../cratekeeper-web/Dockerfile),
  [cratekeeper-web/nginx.conf](../../cratekeeper-web/nginx.conf)).
  Compose builds were not exercised in CI here — run
  `docker compose build api web` before first deploy.

**Outstanding (deferred to manual acceptance):**
- Real-hardware Apple Silicon mood analysis end-to-end run (CLI runs
  locally; the api-container topology is platform-agnostic but unverified).
- Manual acceptance run on a real wedding playlist.
- Drag-and-drop reorder for genre buckets (currently up/down arrows).
- True interactive OAuth flows (the `/settings/auth/*/relink` endpoints
  re-validate file-based MCP creds but do not run the original interactive
  login).

## ⚠️ Credential rotation

The `spotify-mcp/spotify-config.json` and `tidal-mcp/tidal-session.json`
credentials were referenced in agent context during build. Rotate before
sharing this repo: regenerate the Spotify client secret in the dashboard and
re-login Tidal via the MCP server.
