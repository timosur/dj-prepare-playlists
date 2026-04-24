# cratekeeper-web

Local-first React UI for the cratekeeper FastAPI backend.

## Run

```sh
# 1) start backend (in cratekeeper-api/)
uv run uvicorn cratekeeper_api.main:create_app --factory --port 8765

# 2) start the web app
cd cratekeeper-web
npm install
npm run dev
# → http://127.0.0.1:5173
```

The dev server proxies `/api/*` to `http://127.0.0.1:8765`. SSE streams (job
progress + log) connect through the same proxy.

## Implemented (M3 baseline)

- Dashboard: list events, create event with name/date/Spotify URL.
- Event detail: run **fetch / classify / classify-tags** jobs with live SSE
  progress, cost telemetry, log viewer, cancel/retry, job history, quality
  summary, track table.
- Settings: integration health, Anthropic API key + model + prompt-caching
  toggle, fs-roots view, bearer-token entry.

## Not yet implemented (deferred per plan)

- Review / Match / Scan / Analyze / Tag-write / Build-event / Sync step UIs
  (backend handlers for these still pending too — only fetch/classify/
  classify-tags/refetch are wired).
- Genre bucket editor, mood profile editor.
- Tag-write undo / dry-run / audit log surfaces (M4).
- In-app Spotify/Tidal OAuth re-auth flow (currently file-based via MCP
  configs).
