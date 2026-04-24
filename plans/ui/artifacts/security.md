# Security & runtime constraints (M1 output)

## Auth

- **Local-only auth mode in v1.** The backend binds to `127.0.0.1` by default. No login UI.
- A `LOCAL_API_TOKEN` env var (random per-install, generated on first run) is required on every API call as `Authorization: Bearer <token>`. The frontend reads it from a generated `config.json` served alongside the SPA. This stops cross-site requests from a browser tab on a different origin from poking the API.
- CORS: only the frontend origin (`http://127.0.0.1:5173` dev, same-origin in prod build) is allowed.

## Secrets storage

| Secret                          | Storage                                                                  |
| ------------------------------- | ------------------------------------------------------------------------ |
| `LOCAL_API_TOKEN`               | env var (or `~/.config/cratekeeper/api_token`)                           |
| `ANTHROPIC_API_KEY`             | DB `settings` table, encrypted with Fernet using `CRATEKEEPER_SECRET_KEY` |
| Spotify client id/secret/tokens | DB `settings` (Fernet encrypted). Replaces `spotify-mcp/spotify-config.json` over time. |
| Tidal session blob              | DB `settings` (Fernet encrypted). Replaces `tidal-mcp/tidal-session.json`. |

- `CRATEKEEPER_SECRET_KEY` is loaded from the env or auto-generated to `~/.config/cratekeeper/secret.key` on first boot (chmod 600).
- Secrets **never** appear in any API response. Endpoints return `{"configured": true}` flags only. Update endpoints accept the secret in the request body.
- Tokens are decrypted only when handed to the integration adapter at job-dispatch time.

## File-system safety

- `settings.allowed_fs_roots` is a JSON array of absolute paths. Default seed: `["/Volumes/Music", "~/Music/Library", "<repo>/data"]` (expanded).
- Every read/write goes through `security.resolve_safe_path(user_supplied_path)`:
  - resolves `~` and symlinks
  - asserts the resolved path is `is_relative_to` one of `allowed_fs_roots`
  - rejects with HTTP 400 + `error.code = "path_outside_root"` otherwise.
- Tag writing additionally requires:
  - The target file lives under an allowed root.
  - A backup snapshot in `<repo>/data/.tag_backups/<event_slug>/<sha256(path)>.json` exists before the write commits.
  - The job request carries `confirm_write: true` (UI sets this only after the Quality Checks panel is acknowledged).
- Filesystem mutating endpoints (tag-write, build-library, build-event) require an explicit `confirm: true` body field. Without it, return HTTP 412 + the dry-run diff.

## Mount pre-flight

Before dispatching any job that touches the filesystem (`scan-*`, `match`, `analyze-mood`, `apply-tags`, `build-library`, `build-event`):

```text
for root in settings.allowed_fs_roots:
    if root is referenced by the job and not (exists and readable):
        raise MountError(root=root, reason="not_mounted")  → HTTP 503 + structured error
```

The frontend renders `MountError` as a "Music library is not mounted" banner with a "Re-check" button (re-runs the precheck endpoint).

## Rate limits

- Per-IP rate limit: 60 req/min on mutating endpoints (in-memory token bucket; sufficient for single-user local).
- MusicBrainz: shared 1 rps token bucket inside the job runner.
- Anthropic: per-job concurrency limit of 1 inside the `classify-tags` semaphore (the classifier batches 50 tracks/request internally).

## Destructive-operation confirmations

| Operation             | Confirmation contract                                                                               |
| --------------------- | --------------------------------------------------------------------------------------------------- |
| `apply-tags`          | Quality Checks panel must be green or explicitly overridden; `confirm_write=true` body; backup made.|
| `build-event` rebuild | Stale-build banner acknowledged; `confirm=true` body; old build dir renamed `*.bak-<timestamp>`.    |
| `build-library` rebuild | `confirm=true` body required (operation is otherwise additive — no destructive case in v1).       |
| Delete event          | `DELETE` requires `?confirm=true` query param; cascades to `event_tracks`, `event_builds`, `event_fetches`, `job_runs`, `playlist_sync_runs`. |
| Tag undo              | `POST /events/{id}/tag-undo` restores from backup; logged in audit log.                             |

## Audit log (M4)

Schema `audit_log(id, ts, actor='local', action, target_kind, target_id, payload jsonb)`. Every destructive operation, override, and OAuth re-auth writes one row. Read-only API; surfaced in the Settings UI.
