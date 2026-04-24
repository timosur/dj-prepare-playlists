# Cratekeeper — Product Requirements Document

**Status:** v1 shipped (CLI + Web App)
**Owner:** Single-operator (DJ)
**Last updated:** 2026-04-24

## 1. Summary

Cratekeeper is a local-first DJ library management toolkit that turns a Spotify wish playlist into a classified, mood-analyzed, properly tagged, event-ready folder on disk — and (optionally) syncs the result back to Spotify and Tidal as per-event sub-playlists. It runs entirely on the operator's Mac against a local music NAS; there is no hosted/cloud component in v1.

It exists in two shapes that share one engine:

- A **CLI** (`crate`) for scripted/Copilot-driven runs.
- A **localhost web app** (FastAPI + React) that orchestrates the same pipeline with progress tracking, review steps, and undo.

## 2. Problem

Preparing a wedding/party set from a client wish playlist takes hours of manual work:

- Spotify metadata is shallow — no usable BPM/key/mood for set planning.
- Genres on Spotify are noisy and per-artist, not per-track.
- Tracks live across Spotify, Tidal, and a local NAS — matching by hand is tedious.
- DJ software (djay PRO etc.) wants a clean `Genre/Artist - Title.ext` folder with proper ID3/Vorbis tags.
- LLM-assisted set tagging (energy/function/crowd/mood) is powerful but easy to do inconsistently.

The DJ needs **one tool** that does intake → classification → matching → audio analysis → LLM tagging → tag write → folder build → playlist sync, with explicit checkpoints and the ability to undo destructive steps.

## 3. Goals & Non-Goals

### Goals (v1)

- End-to-end pipeline from a Spotify playlist URL to a tagged event folder on disk.
- 18 fixed genre buckets, deterministic and reviewable.
- Audio analysis (BPM, key, energy, mood) via Essentia + TF models, running natively on Apple Silicon.
- LLM-assigned structured tags (energy / function / crowd / mood) via the Anthropic API with prompt caching and pre-flight cost estimate.
- ID3/Vorbis tag writes with **byte-level per-file backup and undo**.
- Per-event sub-playlists synced back to Spotify and Tidal (ISRC-first matching).
- Master library accumulator on disk (`~/Music/Library/Genre/…`).
- Web UI with: dashboard, guided per-event step rail, review lanes, build/sync history, audit log, settings.
- The CLI and web app share one Postgres schema and can be used interchangeably without state drift.

### Non-Goals (v1)

- Multi-user / multi-tenant / cloud hosting.
- Windows or Linux desktop support.
- A music player or live mixing surface — this is a pipeline tool, not a DJ deck.
- Spotify/Tidal master *playlist* (cross-event) management (event sub-playlists only).
- User-editable LLM tag vocabularies (genre buckets are editable; tag vocabularies are fixed in v1).
- Drag-and-drop reorder for genre buckets (up/down arrows only in v1).

## 4. Users & Use Cases

**Primary user:** a single DJ preparing private events (weddings, corporate parties).

**Primary use case:** "I have a Spotify wish playlist for Saturday's wedding. I want a clean, tagged, sorted event folder by Friday with a same-event sub-playlist on Spotify and Tidal."

**Secondary use cases:**

- Run the same pipeline from VS Code Copilot via the `prepare-event` skill (CLI-driven).
- Maintain a global on-disk master library that grows as events are processed.
- Re-tag an existing event after improving the LLM prompt or audio analysis, then rebuild only what changed.

## 5. Scope — Functional Requirements

### 5.1 Pipeline (12 steps, both CLI and Web)

1. **Fetch** — Pull a Spotify playlist into local JSON.
2. **Enrich** *(CLI)* — MusicBrainz genre/year fill-in (rate-limited 1 req/s).
3. **Classify** — Rule-based assignment into 18 genre buckets.
4. **Review** — Surface low-confidence classifications; bulk re-bucket.
5. **Scan** — Index local NAS into Postgres (incremental + full).
6. **Match** — ISRC → exact → fuzzy match Spotify tracks to local files; emit Tidal purchase URLs for misses.
7. **Analyze Mood** — Essentia + TF models (BPM, key, energy, mood probabilities, arousal/valence). Per-track checkpoints; resumable.
8. **Classify Tags (LLM)** — Anthropic Sonnet via the official SDK with prompt caching. Show token/cost estimate before dispatch; surface live token usage during run.
9. **Apply Tags** — Write ID3/Vorbis/MP4 tags in place. Per-file byte-exact backup. `dry_run` available.
10. **Undo Tags** — Restore audio files from the backup snapshots.
11. **Build Event Folder** — Copy (default) or symlink (per-event option) into `Genre/Artist - Title.ext`. `dry_run` shows the diff.
12. **Build Master Library** — Same, but for the global library; dedups across events.
13. **Sync Spotify / Sync Tidal** — Create per-event sub-playlists, ISRC-matched, with click-through URL persisted.

### 5.2 Quality Gate

A pre-flight Quality Checks panel runs before destructive steps (`apply-tags`, `build-event`, `sync-*`). Warnings are advisory; failures require explicit override (typed confirmation phrase). All overrides are written to the audit log.

### 5.3 Stale-Build Invalidation

Re-running `apply-tags` marks downstream library and event-folder builds as **stale**. The UI shows a banner; rebuilds are user-initiated (never automatic — files are large).

### 5.4 Multi-Event

The dashboard lists all active events. Heavy jobs serialize in the backend queue (1 heavy concurrent / 4 light concurrent). Per-event step state is persisted independently.

### 5.5 Settings & Auth

- Spotify and Tidal: in-app re-link buttons (validate file-based credentials in v1; true interactive OAuth deferred).
- Anthropic: API key + model selector + prompt-caching toggle + cumulative cost view.
- Filesystem roots: read-only display.
- Bearer token: editable.
- Genre buckets: reorderable (up/down), editable, with a fallback flag.

### 5.6 Audit Log

Every state-changing action funnels through `services/audit.record(...)` and is queryable via `GET /audit` and the `/audit` UI page (filterable by `target_kind` and `target_id`).

## 6. Non-Functional Requirements

| Area | Requirement |
|------|-------------|
| Platform | macOS (Apple Silicon native). Postgres in Docker. |
| Concurrency | 1 heavy job (mood analysis, tag write) + 4 light jobs concurrent. |
| Crash recovery | Per-track checkpoints in Postgres; jobs resumable from the last completed unit. |
| Reversibility | Tag writes and folder builds support `dry_run`; tag writes have byte-level undo. |
| Security | Bearer-token auth on the API; secrets encrypted at rest with Fernet (`CRATEKEEPER_FERNET_KEY`). CORS restricted to localhost. |
| Rate limits | MusicBrainz throttled to 1 req/s; Spotify/Tidal rely on adapter back-off. |
| Observability | SSE channel per job for progress + logs (with last-event-id replay). Audit log for state changes. |
| Test mode | `CRATEKEEPER_TEST_MODE=true` swaps Spotify/Tidal/Anthropic adapters for mocks. |
| Tests | Backend ≥ green on `uv run pytest -q` against an ephemeral Docker Postgres; frontend `npm run build` 0 errors. |

## 7. Success Metrics (Operator-Level)

- Time from "playlist URL in hand" to "event folder ready" < 1 hour for a 100-track event (excluding human review).
- ≥ 95% of tracks matched to local files for established libraries (ISRC-first).
- Zero unrecoverable tag writes — every `apply-tags` has a working `undo-tags` restore.
- 100% of destructive actions appear in the audit log.

## 8. Open Items / Deferred

- True interactive OAuth flows for Spotify and Tidal (re-link endpoints currently re-validate file-based credentials only).
- Drag-and-drop reorder for genre buckets.
- Real-hardware Apple Silicon mood-analysis acceptance run inside the `api` container.
- Manual end-to-end acceptance on a real wedding playlist.
- Cross-event Spotify/Tidal master playlist management (deferred past v1).
- Hosted multi-user deployment (out of scope).

## 9. References

- [README.md](../README.md) — install, CLI commands, full pipeline walkthrough.
- [DESIGN.md](../DESIGN.md) — visual design system.
- [plans/ui/README.md](../plans/ui/README.md) — v1 plan index.
- [plans/ui/STATUS.md](../plans/ui/STATUS.md) — shipped vs. planned.
- [.github/skills/prepare-event/SKILL.md](../.github/skills/prepare-event/SKILL.md) — Copilot-driven CLI workflow.
