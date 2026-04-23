---
name: prepare-event
description: 'End-to-end pipeline: Spotify wish playlist → classified, mood-analyzed, tagged local event folder ready for DJing. Use when: preparing a wedding, party, or corporate event from a client wish playlist. Requires: spotify MCP server connected, Docker for essentia mood analysis, NAS mounted at /Volumes/Music.'
argument-hint: 'Provide the Spotify playlist URL, event name, and event date'
---

# Prepare Event

Full pipeline from a Spotify wish playlist to a local event folder with files organized by Genre/Mood, tagged and ready for DJing.

## When to Use

- A client sends a Spotify wish playlist for an upcoming event
- You need to prepare a complete DJ set folder from scratch
- Re-running after the wish playlist has been updated

## Required

- **Docker** — all commands run via `docker compose run --rm dj <command>`
- **spotify MCP server** — connected and authenticated
- **NAS mounted** at `/Volumes/Music` (or wherever the music library lives)
- **docker-compose.yml** mounts: `/Volumes/Music:/music:ro`, `~/Music/Library:/library`, `./data:/data`

## Input

The user provides:
- **Spotify playlist** — URL (e.g., `https://open.spotify.com/playlist/...`) or playlist ID
- **Event name** — e.g., "Wedding Tim & Lea"
- **Event date** — e.g., "2026-04-22"

## Procedure

All commands use Docker. The base command is:
```bash
docker compose run --rm dj <command> [args]
```

### Step 1: Fetch Tracks from Spotify

```bash
docker compose run --rm dj fetch "<playlist-url>" --output /data/<slug>.json
```

Use a URL-safe slug for the filename (e.g., `hochzeitsmaeusse`). Report the track count to the user.

### Step 2: Enrich with MusicBrainz

```bash
docker compose run --rm dj enrich /data/<slug>.json
```

This queries MusicBrainz for missing genres and original release years via ISRC lookup. Rate-limited at ~1 req/sec. Also computes era labels (80s, 90s, etc.) for all tracks.

Report: how many tracks enriched, how many had no tags.

### Step 3: Classify into Genre Buckets

```bash
docker compose run --rm dj classify /data/<slug>.json
```

This creates `/data/<slug>.classified.json` with genre buckets. Show the classification summary table to the user.

**Genre buckets** (13 total, ordered by priority): Schlager, DnB, Techno/Melodic, House/Dance, Hip-Hop/R&B, Latin/Reggaeton, Rock/Indie, 80s, 90s, 2000s, Oldschool, Ballads/Slow, Party Hits (fallback).

### Step 4: Review Classification

```bash
docker compose run --rm dj review /data/<slug>.classified.json
```

Show medium/low confidence tracks. Ask user: *"Does this look right? Want me to move any tracks between categories?"*

If the user wants changes, edit the `.classified.json` directly to change `bucket` values. **Wait for user confirmation before proceeding.**

### Step 5: Scan NAS Library

```bash
docker compose run --rm dj scan /music
```

Indexes all audio files from the NAS into SQLite (`/data/local-library.db`). Uses `os.walk` for streaming progress over SMB. Incremental by default — skips already-indexed files on re-runs.

If the DB already exists and is recent, this step can be skipped (ask user).

### Step 6: Match Tracks to Local Files

```bash
docker compose run --rm dj match /data/<slug>.classified.json --db /data/local-library.db
```

Matches Spotify tracks to local files using three strategies:
1. **ISRC** — exact match (fastest, most accurate)
2. **Artist + Title** — normalized exact match
3. **Fuzzy** — token sort ratio ≥ 85%

Report the match results table. If many tracks are unmatched, suggest the user check their library or buy missing tracks.

### Step 7: Analyze Mood (essentia)

```bash
docker compose run --rm dj analyze-mood /data/<slug>.classified.json
```

Uses essentia (Linux x86_64 via Docker) to extract BPM, energy, danceability from each matched audio file. Classifies into mood categories using genre-specific thresholds:

**Moods**: Chill, Warm-Up, Groovy, Energetic, Peak, Romantic

Show the mood distribution table.

**Important**: The `local_path` values in the JSON must be accessible inside the container. If `build-library` was run before, paths point to `/library/...`. If only `match` was run, paths point to `/music/...`. Mount accordingly.

### Step 8: Build Master Library

```bash
docker compose run --rm dj build-library /data/<slug>.classified.json --target /library
```

Copies matched files into `~/Music/Library/Genre/Mood/Artist - Title.ext`. Skips files that already exist. Updates `local_path` in the JSON to the new library location.

Default target is `~/Music/Library` (mounted as `/library` in Docker).

### Step 9: Build Event Folder

```bash
docker compose run --rm dj build-event /data/<slug>.classified.json --output /library/Events/<EventName>/
```

Copies files into an event-specific folder with the same `Genre/Mood/` structure. Creates `_missing.txt` for unmatched tracks.

### Step 10: Tag Audio Files

```bash
docker compose run --rm dj tag /data/<slug>.classified.json
```

Writes genre, mood, and era into ID3/FLAC tags:
- **MP3**: TCON (genre), GRP1/TIT1 (mood), COMM (era)
- **FLAC**: genre, grouping, mood, era, comment fields

### Step 11: Report to User

Summarize:
- Total tracks processed
- Match rate (ISRC / exact / fuzzy / missing)
- Mood distribution
- Library location (`~/Music/Library`)
- Event folder location
- Missing tracks list

## Quick Re-run (Updated Playlist)

If the source playlist was updated:
```bash
docker compose run --rm dj fetch "<playlist-url>" --output /data/<slug>.json
docker compose run --rm dj enrich /data/<slug>.json
docker compose run --rm dj classify /data/<slug>.json
docker compose run --rm dj match /data/<slug>.classified.json
docker compose run --rm dj analyze-mood /data/<slug>.classified.json
docker compose run --rm dj build-library /data/<slug>.classified.json
docker compose run --rm dj build-event /data/<slug>.classified.json --output /library/Events/<EventName>/
docker compose run --rm dj tag /data/<slug>.classified.json
```

The scan step can be skipped if the NAS library hasn't changed (incremental indexing handles additions).

## Quality Checks

- [ ] All tracks from the source playlist are accounted for
- [ ] Classification reviewed and confirmed by user before proceeding
- [ ] Match rate is reasonable (>50% for a well-stocked library)
- [ ] Mood analysis completed for all matched tracks
- [ ] Files are real copies (not symlinks) in the library and event folders
- [ ] Tags written successfully
- [ ] Missing tracks list provided to user for manual download
