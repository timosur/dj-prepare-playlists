# Architecture (M1 output)

Local-first FastAPI + React app orchestrating the existing `cratekeeper` Python pipeline. Single user, single host (macOS).

## Bounded contexts

| Context              | Owns                                                                  | Reuses (CLI module)                                              |
| -------------------- | --------------------------------------------------------------------- | ---------------------------------------------------------------- |
| Events               | `events`, `event_tracks`, `event_fetches`                             | `models.EventPlan` / `Track` (mapped, not duplicated)            |
| Tracks (library)     | existing `tracks` table (canonical)                                   | `local_scanner` (read+write owner)                               |
| Workflow Jobs        | `job_runs`, `job_checkpoints` + in-process queue                      | `matcher`, `mood_analyzer`, `classifier`, `tag_writer`, `event_builder`, `library_builder` |
| Playlist Integrations| `playlist_sync_runs`, OAuth tokens (in `settings`)                    | `spotify_client`, `tidal_client` (extended, not replaced)        |
| Tag Classification   | per-track LLM tags + `genre_suggestion` on `event_tracks`             | new `tag_classifier` module (Anthropic SDK)                      |
| Settings             | `settings`, `genre_buckets`, `mood_thresholds`                        | `genre_buckets`, `mood_config` (read from DB instead of constants)|

## CLI command → service map

| `crate` command         | Backend job type        | Service module (in `cratekeeper_api`)                                        |
| ----------------------- | ----------------------- | ---------------------------------------------------------------------------- |
| `fetch`                 | `fetch`                 | `services.events.fetch_playlist`  → `integrations.spotify.SpotifyAdapter`    |
| `enrich` (implicit `--enrich` on classify) | `enrich` | `services.enrichment.run`         → `integrations.musicbrainz` (rate-limited)|
| `classify`              | `classify`              | `services.classification.run`     → CLI `classifier.classify_tracks`         |
| `review`                | (interactive — UI only) | n/a (state mutations through `PATCH /events/{id}/tracks/{id}`)               |
| `scan`                  | `scan-incremental` / `scan-full` | `services.scan.run`        → CLI `local_scanner.scan_directory`           |
| `match`                 | `match`                 | `services.matching.run`           → CLI `matcher`                            |
| `analyze-mood`          | `analyze-mood`          | `services.mood.run`               → CLI `mood_analyzer` (subprocess)         |
| `classify-tags` (NEW)   | `classify-tags`         | `services.tag_classifier.run`     → new `integrations.anthropic.LLMTagClient`|
| `apply-tags`            | `apply-tags`            | `services.tagging.run`            → CLI `tag_writer` (with backup)           |
| `build-library`         | `build-library`         | `services.library.build`          → CLI `library_builder`                    |
| `build-event`           | `build-event`           | `services.event_folder.build`     → CLI `event_builder`                      |
| `match --tidal-urls`    | (read-only artifact)    | rendered from `event_tracks.match_status` + `tidal_client.purchase_url(...)` |
| sync sub-playlists      | `sync-spotify` / `sync-tidal` | `services.sync.run`         → `spotify_client` / `tidal_client`           |

Direct invocation vs adapter:

- **Direct invocation** (no adapter wrapper): pure-Python modules with no I/O surprises — `classifier`, `genre_buckets`, `models`. The job handler imports them directly.
- **Adapter** (Protocol + concrete + mock): every external network/process boundary — Spotify, Tidal, MusicBrainz, Anthropic, mood subprocess, filesystem scan, tag writer. Adapters are injected through a `Container` so tests can swap in fakes.

## Process topology

- Single FastAPI process. Uvicorn worker. In-process `asyncio.Queue` job runner — no separate worker process in v1.
- Postgres in Docker (existing `docker-compose.yml`).
- Mood analysis (essentia + TF) runs as a subprocess from the same process; macOS native (Apple Silicon) — the old `crate` Docker container is no longer required by the web app.
- Background tasks survive a request, but **not** a process restart — recovery is via DB checkpoints.

## Concurrency rules

- One **heavy** job (`scan-full`, `analyze-mood`, `build-library`, `build-event`) globally — `asyncio.Semaphore(1)`.
- **Light** jobs (`enrich`, `classify`, `classify-tags`, `match`, `sync-*`) parallelize, capped at `Semaphore(4)` per job-type to keep API responsive.
- Cross-cutting **MusicBrainz token bucket** (1 rps shared across jobs).

## CLI/web coexistence contract

- Web app and CLI share Postgres. Migrations are owned by Alembic in `cratekeeper-api`; the CLI's existing `CREATE TABLE IF NOT EXISTS` blocks become idempotent no-ops once migrations have run.
- New tables are *additive*. Existing `tracks` columns are not renamed or removed.
- Long-running web jobs hold no exclusive DB locks across requests; they take row-level locks only inside short transactions.
- The CLI continues to consume `data/<slug>.json` artifacts. The web app writes the same artifacts (single source of truth on disk + DB).
