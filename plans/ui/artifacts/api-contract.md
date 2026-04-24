# API contract draft (M1 output)

All endpoints are JSON, prefix `/api/v1`. Auth: `Authorization: Bearer <LOCAL_API_TOKEN>` (M1 design — implemented in M2).
Errors use [RFC 7807 Problem Details](https://www.rfc-editor.org/rfc/rfc7807): `{type, title, status, detail, code, ...}`.

## Health

| Method | Path                       | Purpose                                  |
| ------ | -------------------------- | ---------------------------------------- |
| GET    | `/health`                  | liveness                                  |
| GET    | `/health/mounts`           | run mount pre-flight; returns per-root status |

## Events

| Method | Path                                              | Purpose                                                |
| ------ | ------------------------------------------------- | ------------------------------------------------------ |
| GET    | `/events`                                         | list events (dashboard)                                |
| POST   | `/events`                                         | create event (`{name, date, source_playlist_url, slug?}`) |
| GET    | `/events/{id}`                                    | event detail incl. counts per workflow stage           |
| PATCH  | `/events/{id}`                                    | rename / re-date / change slug                         |
| DELETE | `/events/{id}?confirm=true`                       | cascade-delete                                         |
| GET    | `/events/{id}/tracks`                             | paginated event tracks (filters: `confidence`, `bucket`, `match_status`, `acquire_later`) |
| PATCH  | `/events/{id}/tracks/{track_id}`                  | review actions: re-bucket, set `acquire_later`, accept/ignore `genre_suggestion` |
| POST   | `/events/{id}/tracks/bulk`                        | bulk re-bucket / re-classify / set tag fields          |
| GET    | `/events/{id}/quality-checks`                     | structured pre-flight result                           |
| GET    | `/events/{id}/builds`                             | build artifacts (library + event-folder) with `is_stale` |
| GET    | `/events/{id}/missing.txt`                        | downloadable `_missing.txt` artifact                   |
| POST   | `/events/{id}/refetch`                            | enqueues `fetch` in diff mode → returns `{job_id, diff: {added, removed, unchanged}}` (200 once diff computed; downstream re-runs accept `?track_ids=...`) |
| GET    | `/events/{id}/fetches`                            | history of fetch runs                                  |
| POST   | `/events/{id}/tag-undo`                           | restore pre-write tag bytes from backup                |

## Jobs

Job lifecycle: `queued → running → succeeded | failed | cancelled`.

| Method | Path                                  | Purpose                                                          |
| ------ | ------------------------------------- | ---------------------------------------------------------------- |
| POST   | `/events/{id}/jobs`                   | enqueue a job: `{type, params}`. Returns `{job_id, status}`.     |
| GET    | `/jobs`                               | filter by `event_id`, `type`, `status`                           |
| GET    | `/jobs/{id}`                          | full job detail incl. `summary` blob and `checkpoints_completed` |
| POST   | `/jobs/{id}/cancel`                   | cooperative cancel                                               |
| POST   | `/jobs/{id}/resume`                   | re-enqueue with `resume_from = last checkpoint`                  |

Job types (v1): `fetch`, `enrich`, `classify`, `scan-incremental`, `scan-full`, `match`, `analyze-mood`, `classify-tags`, `apply-tags`, `build-library`, `build-event`, `sync-spotify`, `sync-tidal`.

## SSE

| Method | Path                                  | Stream                                                |
| ------ | ------------------------------------- | ----------------------------------------------------- |
| GET    | `/jobs/{id}/events/progress`          | progress events (see [sse-events.md](sse-events.md))  |
| GET    | `/jobs/{id}/events/log`               | structured log lines                                  |
| GET    | `/events/{id}/jobs/stream`            | dashboard fan-out: every job state-change for the event |

Two channels per job (progress vs log) so the UI can subscribe to log noise independently of the progress bar.

## Settings

| Method | Path                                  | Purpose                                                           |
| ------ | ------------------------------------- | ----------------------------------------------------------------- |
| GET    | `/settings`                           | non-secret settings + `{anthropic_configured, spotify_configured, tidal_configured}` flags |
| PUT    | `/settings/anthropic`                 | `{api_key, model?, prompt_caching?}`                              |
| PUT    | `/settings/fs-roots`                  | `{roots: [...]}` — validated against existence                    |
| GET    | `/settings/genre-buckets`             | DB-backed bucket list (ordered)                                   |
| PUT    | `/settings/genre-buckets`             | full replace; preserves order                                     |
| GET    | `/settings/mood-thresholds`           | per-genre thresholds                                              |
| PUT    | `/settings/mood-thresholds`           | full replace                                                      |
| GET    | `/settings/tag-vocabularies`          | read-only `{energy, function, crowd, mood}` lists                 |

## OAuth

| Method | Path                                  | Purpose                                                           |
| ------ | ------------------------------------- | ----------------------------------------------------------------- |
| GET    | `/oauth/spotify/start`                | returns `{authorize_url, state}`                                  |
| GET    | `/oauth/spotify/callback`             | Spotify redirect target; persists tokens; redirects to `/settings` |
| GET    | `/oauth/tidal/start`                  | returns `{authorize_url, state}`                                  |
| GET    | `/oauth/tidal/callback`               | Tidal redirect target; persists session                           |

## Audit log (M4)

| Method | Path                                  | Purpose                       |
| ------ | ------------------------------------- | ----------------------------- |
| GET    | `/audit-log`                          | paginated, filterable         |
