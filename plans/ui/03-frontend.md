## Milestone 3 — Phase 3: Frontend

Build the React UI: shell, event workflow, master library management, and settings.

**Depends on**: Milestone 2 for the event workflow + master library UIs (need real API + SSE to integrate against); the shell only needs the API contract from Milestone 1.
**Unblocks**: Milestone 4 (hardening relies on UI surfaces for audit log, failure-recovery actions, tag undo, etc.).

### Work items

1. **Frontend shell** (depends on Milestone 1 API contract): build the React app shell with hybrid UX — dashboard overview + guided event workflow entry. The dashboard lists all active events (each with event name + auto-derived slug, editable); a user can switch between events freely (multi-event concurrent UX). Heavy jobs still serialize in the backend queue. **Tooling, committed**: Vite + React + TailwindCSS + TypeScript; TanStack Query for server state (fits SSE + polling patterns); TanStack Router or React Router; react-hook-form for forms.

2. **Event workflow UI** (depends on Milestone 2 backend + shell): step views for Intake, Enrich, Classify, Review, Scan/Match, Analyze, Tagging, Build Event Folder, Spotify/Tidal Event Sync. Add confidence filters and manual bucket overrides.

   **Per-step surfaces**:
   - **Intake**: paste Spotify playlist URL *or* raw playlist ID + event name + date; slug auto-derived (URL-safe), editable.
   - **Enrich**: show a live ETA (1 req/sec × pending track count) alongside the progress bar so users know MusicBrainz is slow by design, not stuck.
   - **Review**: defaults to low-confidence-first ordering (mirrors the skill's `crate review` behavior). Confidence filters + bulk re-bucket / bulk skip / bulk re-classify at a new threshold — 100-track playlists are typical. **Blocking gate**: the guided workflow does not auto-advance past Review; the user must explicitly click "Continue to Scan" to proceed.
   - **Scan**: incremental by default (skips already-indexed files). Show last-scan timestamp; if recent, render a "Skip (library unchanged)" one-click action. Explicit "Full rescan" control behind a confirmation ("this may take several minutes for large libraries"). Pre-dispatch mount check: if `/Volumes/Music` is unreachable, show a "Music library is not mounted" banner with a re-check button instead of failing silently.
   - **Match**: after matching, surface matched vs. unmatched and render the same Tidal purchase URLs that `crate match --tidal-urls` produces for each unmatched track (clickable → opens Tidal).
   - **Missing-tracks recovery**: per-track actions — open Tidal URL, "I've added it, rescan this track", "mark as acquire-later" (flows into `_missing.txt` at build time). Manual path override + in-UI file upload are out of scope for v1; rescan is the recovery path.
   - **Analyze**: after completion, render the skill's energy distribution table (low / mid / high counts) and BPM histogram as first-class UI — not just log lines.
   - **Tagging**: before dispatching the LLM classifier job, show a token/cost estimate (e.g. "~12k input tokens, est. $0.04") so the user can confirm; during the run, render live token usage + cache-hit ratio from the log channel. After completion, two review surfaces: (a) the tag-corrections UI (reuses Review's bulk actions for tag fields), and (b) a **separate "LLM suggests reclassifying" lane** listing tracks where the LLM returned a `genre_suggestion` different from the current bucket — user bulk-accepts or ignores. Both applied before `apply-tags` commits.
   - **Build Event Folder**: copy is the default; a per-event "use symlinks" toggle is available for advanced users (symlinks break portability to external drives, shown in a warning). The Quality Checks pre-flight flags symlink use as a warning, not a failure.
   - **Stale-build banner**: if `event_builds.is_stale=true` (triggered by a tag re-run after a prior build), the Build Library and Build Event Folder steps show a "Tags changed since last build — rebuild to propagate" banner with a one-click rebuild action.
   - **Quality Checks pre-flight panel**: before dispatching tag-write, build-event, or sync, pop a checklist panel rendering the backend's quality-checks endpoint (all tracks accounted for, match ≥ 50%, audio analysis complete, LLM tags present, symlink warning if applicable, missing tracks listed). Warnings are advisory; failures block with an explicit "Override and proceed" button that records the override in the audit log.
   - **Per-job log viewer** alongside the progress bar on every step.
   - **Completion summary page** at the end of the pipeline: total tracks, match-rate breakdown (ISRC / exact / fuzzy / missing), energy distribution, library/event-folder locations, missing tracks list — matches the skill's step 12 report. `_missing.txt` is linked as a downloadable/viewable artifact.

   **Pipeline re-run (playlist updated)**: a "Re-fetch from Spotify" action on any event. Backend detects added/removed/unchanged tracks and the UI shows a diff. User confirms; downstream steps (enrich/classify/match/analyze/tag) re-run only for affected tracks. Scan step is skipped unless the user explicitly triggers it. Each re-run is recorded in `job_runs` history for the event.

3. **Master library UI** (depends on Milestone 2 backend + shell): run and monitor `build-library` jobs that accumulate files into `~/Music/Library/Genre/…`. Show library contents grouped by bucket with track counts + disk usage; filter/search across the accumulated library. History of build-library runs with outcomes. No Spotify/Tidal master-playlist management in v1 — that's deferred.

4. **Settings / admin UI** (parallel with event + master UIs): integrations settings, local paths, genre bucket editor, mood profile editor, safety toggles.
   - Tidal re-auth lives here: a "Re-connect Tidal" button that kicks off the in-app OAuth flow (redirect → backend callback → return to the UI) and shows the current session health.
   - Anthropic section: API key entry (stored encrypted server-side), model selector (default `claude-sonnet-4-6`), prompt-caching toggle (default on), and a cumulative token/cost readout across jobs.
   - Back the bucket/mood config with DB tables seeded from the current hardcoded constants in [genre_buckets.py](../../cratekeeper-cli/cratekeeper/genre_buckets.py) and [mood_config.py](../../cratekeeper-cli/cratekeeper/mood_config.py). Keep the CLI reading from the same source — single source of truth. The bucket editor supports drag-reorder; order is semantically meaningful ("first match wins" in classification).
   - Tag vocabularies (`energy` / `function` / `crowd` / `mood`) render as read-only reference in this section — these are fixed in v1 to keep the LLM prompt stable; users can see them but not edit them.
   - Include a macOS-aware filesystem picker with guidance on Full Disk Access for `/Volumes/...` roots.

### Acceptance

- Dashboard loads with an empty-state and an active-events list; switching between two in-flight events preserves per-event state.
- A user can drive an event end-to-end through the guided workflow in the browser: intake → enrich → classify → review → match → analyze → tag → build → sync.
- Review defaults to low-confidence-first on first open.
- Scan defaults to incremental; "Full rescan" requires confirmation and triggers a full index rebuild.
- Match view renders clickable Tidal URLs for unmatched tracks.
- Analyze completion shows energy distribution and BPM histogram as UI surfaces.
- Event folder build defaults to copy; toggling symlinks on a second event works without affecting the first.
- Tidal re-auth button completes an in-app OAuth round trip and the session-health indicator flips to healthy.
- Progress and log events render live from SSE during long jobs.
- Bulk re-bucket and bulk re-classify work on a 100-track fixture; tagging bulk-review applies to the LLM-assigned tags.
- Missing-tracks recovery flow: click Tidal URL (external), add the file locally, trigger rescan, and the previously-missing track resolves; alternatively mark-as-acquire-later keeps the track out of the event folder cleanly.
- Updating the source Spotify playlist and hitting Re-fetch produces a diff view; confirming runs only affected downstream steps and records a new job run.
- Pipeline completion summary renders with match breakdown, energy distribution, library/event-folder paths, and missing tracks — matching the skill's step 12 report; `_missing.txt` is clickable.
- Master library view lists accumulated files by bucket with counts and disk usage.
- Editing a genre bucket in the UI is visible to the CLI on the next run (shared config source); reordering buckets changes classification results on the next classify run.
- Filesystem picker refuses paths outside allowed roots.
- Review step does not auto-advance; clicking "Continue" is required.
- Enrich step shows a reasonable ETA (not just a spinner) derived from the 1 rps rate limit.
- Dispatching a scan with `/Volumes/Music` unmounted shows a structured error, not an empty-result success.
- After re-running Tagging on an event with an existing build, the build steps show the stale banner and a one-click rebuild re-propagates tags to the files.
- Quality Checks pre-flight blocks tag-write until either all checks are green or an explicit override is confirmed; overrides are recorded in the audit log.
- LLM genre suggestions appear in their own review lane after Tagging; bulk-accept moves tracks between buckets, bulk-ignore leaves buckets untouched.
