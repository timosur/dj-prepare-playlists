# SSE event schemas (M1 output)

All SSE responses use `Content-Type: text/event-stream` with `event:` + `data:` (JSON). Every event carries `job_id` so the client can demultiplex.

## `/jobs/{id}/events/progress`

```text
event: progress
data: {"job_id":"<uuid>","ts":"2025-04-24T10:11:12.345Z","i":34,"total":100,"phase":"matching","item":{"track_id":"sp_abc","display":"\"Song\" by Artist"},"result":{"match":"isrc","confidence":"high"}}

event: stage
data: {"job_id":"<uuid>","ts":"...","stage":"running","detail":"started"}

event: stage
data: {"job_id":"<uuid>","ts":"...","stage":"succeeded","summary":{ /* job-type specific */ }}

event: stage
data: {"job_id":"<uuid>","ts":"...","stage":"failed","error":{"code":"mount_not_ready","message":"/Volumes/Music not readable"}}

event: heartbeat
data: {"job_id":"<uuid>","ts":"..."}     # every 15s when idle
```

Notes:
- `progress` events: `i / total` are the canonical progress numerator/denominator forwarded from the existing `progress_callback(i, total, track, result)` hooks.
- `phase` partitions a multi-phase job (e.g. `match` has phases `isrc`, `exact`, `fuzzy`).
- `stage` events bracket the run; `succeeded` carries the persisted `job_runs.summary` blob verbatim.
- Client should reconnect with `Last-Event-ID` to resume — server replays from the in-memory ring buffer (last 200 events per channel).

## `/jobs/{id}/events/log`

```text
event: log
data: {"job_id":"<uuid>","ts":"...","level":"info","msg":"MusicBrainz: Bob Marley & The Wailers → reggae, ska","src":"enrich"}

event: log
data: {"job_id":"<uuid>","ts":"...","level":"warning","msg":"ISRC mismatch on track sp_abc; falling back to fuzzy","src":"matcher"}

event: cost
data: {"job_id":"<uuid>","ts":"...","input_tokens":12041,"output_tokens":2384,"cache_read":0,"cache_write":1820,"est_usd":0.041}
```

`cost` is emitted only by `classify-tags`; the UI uses it to render running spend.

## `/events/{id}/jobs/stream`

Fan-out of `stage` events for **every** job belonging to the event (no per-track `progress`). Powers the dashboard.

```text
event: job_stage
data: {"event_id":"<uuid>","job_id":"<uuid>","type":"classify","stage":"succeeded","ts":"..."}
```

## Per-job-type `summary` payloads

| Job type        | Summary keys                                                                                          |
| --------------- | ------------------------------------------------------------------------------------------------------ |
| `fetch`         | `playlist_name`, `track_count`, `new_isrc_count`                                                       |
| `enrich`        | `attempted`, `enriched`, `no_tags`, `errors`                                                           |
| `classify`      | `bucket_counts: {bucket: n}`, `low_confidence: n`, `fallback: n`                                       |
| `scan-*`        | `new`, `skipped`, `updated`, `removed`, `duration_s`                                                   |
| `match`         | `isrc`, `exact`, `fuzzy`, `missing`, `match_rate`                                                      |
| `analyze-mood`  | `analyzed`, `errors`, `energy_dist:{low,mid,high}`, `bpm_histogram:[{bucket,count}]`                   |
| `classify-tags` | `tagged`, `cache_hit_ratio`, `input_tokens`, `output_tokens`, `est_usd`, `genre_suggestions: n`        |
| `apply-tags`    | `written`, `skipped`, `backed_up`                                                                       |
| `build-library` | `bucket_dirs`, `total_files`, `total_bytes`                                                            |
| `build-event`   | `mode: copy\|symlink`, `total_files`, `total_bytes`, `missing: n`                                      |
| `sync-spotify`  | `playlists_created`, `playlists_updated`, `tracks_added`                                               |
| `sync-tidal`    | `playlists_created`, `playlists_updated`, `tracks_added`, `unmatched: n`                               |
| `refetch`       | `added: n`, `removed: n`, `unchanged: n`                                                               |
