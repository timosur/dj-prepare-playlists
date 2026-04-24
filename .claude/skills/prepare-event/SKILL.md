---
name: prepare-event
description: Use when preparing a wedding, party, or corporate event from a client's Spotify wish playlist. End-to-end pipeline that turns a Spotify playlist URL into a classified, mood-analyzed, LLM-tagged local event folder ready for DJing. Requires Spotify MCP server connected, Docker for essentia audio analysis, and NAS mounted at /Volumes/Music.
---

# Prepare Event

Full pipeline from a Spotify wish playlist to a local event folder with files organized by Genre/, tagged with structured metadata and ready for DJing.

## When to Use

- A client sends a Spotify wish playlist for an upcoming event
- You need to prepare a complete DJ set folder from scratch
- Re-running after the wish playlist has been updated

## Arguments to Gather from User

Before running, make sure you have:

- **Spotify playlist** — URL (e.g., `https://open.spotify.com/playlist/...`) or playlist ID
- **Event name** — e.g., "Wedding Tim & Lea"
- **Event date** — e.g., "2026-04-22"

If any are missing, ask the user for them before starting.

## Required

- **Python ≥ 3.11** with `cratekeeper-cli` installed locally (`pip install -e ./cratekeeper-cli`)
- **Docker** — needed for audio analysis (essentia + TF models require Linux x86_64)
- **PostgreSQL** — running locally or via Docker; default connection: `postgresql://dj:dj@localhost:5432/djlib` (override with `DATABASE_URL` env var)
- **spotify MCP server** — connected and authenticated
- **NAS mounted** at `/Volumes/Music` (or wherever the music library lives)

## Path Reference

| Context | data dir | NAS music | Library |
|---------|----------|-----------|---------|
| **Local** | `data/` | `/Volumes/Music` | `~/Music/Library` |
| **Docker** (analysis only) | `/data` | `/music` | `/library` |

## Genre Buckets (18)

Ordered by specificity (first match wins):
Schlager, Drum & Bass, Hardstyle, Melodic Techno, Techno, Minimal / Tech House,
Deep House, Progressive House, Trance, House, EDM / Big Room, Dance / Hands Up,
Hip-Hop / R&B, Latin / Global, Disco / Funk / Soul, Rock, Ballads / Slow, Pop (fallback).

Era (80s, 90s, 2000s, etc.) is NOT a genre — it's derived from release_year and stored as a tag in the comment field.

## Tag System

Structured tags are stored in the ID3 comment field (or FLAC comment) with this format:
```
era:90s; energy:high; function:floorfiller,singalong; crowd:mixed-age; mood:feelgood,euphoric
```

- **energy**: low, mid, high
- **function**: floorfiller, singalong, bridge, reset, closer, opener
- **crowd**: mixed-age, older, younger, family
- **mood**: feelgood, emotional, euphoric, nostalgic, romantic, melancholic, dark, aggressive, uplifting, dreamy, funky, groovy

Tags are assigned by the LLM classifier using audio analysis + metadata as input.

## Procedure

Most commands run locally. Audio analysis uses Docker (essentia + TF models require Linux x86_64).

```bash
# Local commands
crate <command> [args]

# Docker (audio analysis only)
docker compose run --rm crate <command> [args]
```

### Step 1: Fetch Tracks from Spotify

```bash
crate fetch "<playlist-url>" --output data/<slug>.json
```

Use a URL-safe slug for the filename (e.g., `hochzeitsmaeusse`). Report the track count to the user.

### Step 2: Enrich with MusicBrainz

```bash
crate enrich data/<slug>.json
```

Queries MusicBrainz for missing genres and original release years via ISRC lookup. Rate-limited at ~1 req/sec.

Report: how many tracks enriched, how many had no tags.

### Step 3: Classify into Genre Buckets

```bash
crate classify data/<slug>.json
```

Creates `data/<slug>.classified.json` with genre buckets and era labels. Show the classification summary table to the user.

### Step 4: Review Classification

```bash
crate review data/<slug>.classified.json
```

Show low confidence tracks. Ask user: *"Does this look right? Want me to move any tracks between categories?"*

If the user wants changes, edit the `.classified.json` directly to change `bucket` values. **Wait for user confirmation before proceeding.**

### Step 5: Scan NAS Library

```bash
crate scan /Volumes/Music
```

Indexes all audio files from the NAS into PostgreSQL. Incremental by default — skips already-indexed files on re-runs.

Use `--full` flag for a complete re-scan. If the DB is already populated and recent, this step can be skipped (ask user).

### Step 6: Match Tracks to Local Files

```bash
crate match data/<slug>.classified.json --tidal-urls
```

Matches Spotify tracks to local files using: ISRC → exact artist+title → fuzzy match (≥85%).

Report the match results table. If many tracks are unmatched, suggest the user check their library.

### Step 7: Analyze Audio (essentia + TF) — Docker required

```bash
docker compose run --rm crate analyze-mood /data/<slug>.classified.json
```

Uses essentia + TensorFlow models to extract:
- **Basic**: BPM, energy (RMS 0-1), danceability, loudness (LUFS), key
- **ML mood classifiers**: happy, party, relaxed, sad, aggressive (0-1 probability each)
- **Arousal/Valence**: 1-9 scale (DEAM model)
- **Voice/Instrumental**: binary classification

Sets preliminary energy classification (low/mid/high) from RMS energy. Show the energy distribution table.

**Important**: This is the only step that requires Docker. The `local_path` values in the JSON use host paths. Docker volume mappings: `/Volumes/Music:/music:ro`, `~/Music/Library:/library`.

### Step 8: Classify Tags via Sub-Agent

Use the `Agent` tool to classify tags. Build a prompt from the classified JSON containing all track metadata and audio analysis, then apply results with `crate apply-tags`.

**8a. Build the sub-agent prompt**

Read `data/<slug>.classified.json` and build a track summary for the prompt. For each track extract: id, name, artists, bucket, era, bpm, key, audio_energy, audio_mood, arousal, valence.

**8b. Call the sub-agent**

Invoke the `Agent` tool with `subagent_type: "general-purpose"`:

```
Agent({
  description: "Classify DJ tags for tracks",
  subagent_type: "general-purpose",
  prompt: `You are a professional wedding & event DJ assistant. Classify each track with structured tags.

Valid values:
- energy: low, mid, high
- function: floorfiller, singalong, bridge, reset, closer, opener (pick 1-3)
- crowd: mixed-age, older, younger, family (pick 1-2)
- mood_tags: feelgood, emotional, euphoric, nostalgic, romantic, melancholic, dark, aggressive, uplifting, dreamy, funky, groovy (pick 1-3)
- genre_suggestion: null, or one of the 18 genre buckets if the current bucket is clearly wrong

Rules:
- "floorfiller" = guaranteed dance track for a wide audience
- "singalong" = tracks most people know the lyrics to
- "bridge" = transitional track between energy levels or genres
- "reset" = palate cleanser, calm moment
- "opener"/"closer" = suitable for opening or closing a set segment
- For crowd: "mixed-age" means works for all ages, "older" skews 40+, "younger" skews under 30
- Use audio data (BPM, energy, mood scores, arousal/valence) to inform choices

Tracks:
${trackLines}

Return ONLY a JSON array, one object per track:
[{"id": "...", "energy": "...", "function": [...], "crowd": [...], "mood_tags": [...], "genre_suggestion": null}, ...]

Do not include any explanation, just the JSON array.`
})
```

Where `trackLines` is built like:
```
1. id=ABC | "Song Name" by Artist | bucket=Pop | era=2020s | bpm=120 | key=C major | audio_energy=0.5 | mood: happy=0.8 party=0.6 | arousal=6.2 | valence=7.1
```

**8c. Save the response and apply**

Save the sub-agent's JSON response to `data/<slug>.tags.json`, then run:

```bash
crate apply-tags data/<slug>.classified.json data/<slug>.tags.json
```

This validates all tag values and writes them into the classified JSON. Report the results to the user.

### Step 9: Tag Audio Files

```bash
crate tag data/<slug>.classified.json
```

Writes metadata into ID3/FLAC tags:
- **Genre** (TCON / genre): bucket name
- **BPM** (TBPM / bpm): beats per minute
- **Key** (TKEY / initialkey): musical key
- **Comment** (COMM / comment): structured tags string

**Important**: Tagging must happen before building library/event folders so that copies contain the tags.

### Step 10: Build Master Library

```bash
crate build-library data/<slug>.classified.json --target ~/Music/Library
```

Copies matched files into `~/Music/Library/Genre/Artist - Title.ext`. Skips files without bucket. Updates `local_path` in the JSON.

### Step 11: Build Event Folder

```bash
crate build-event data/<slug>.classified.json --output ~/Music/Events/<EventName>/
```

Copies files into an event-specific folder with `Genre/` structure. Creates `_missing.txt` for unmatched tracks.

### Step 12: Report to User

Summarize:
- Total tracks processed
- Match rate (ISRC / exact / fuzzy / missing)
- Energy distribution
- Library location (`~/Music/Library`)
- Event folder location
- Missing tracks list

## Quick Re-run (Updated Playlist)

If the source playlist was updated:
```bash
crate fetch "<playlist-url>" --output data/<slug>.json
crate enrich data/<slug>.json
crate classify data/<slug>.json
crate match data/<slug>.classified.json --tidal-urls
docker compose run --rm crate analyze-mood /data/<slug>.classified.json
# classify tags via Agent tool + crate apply-tags (see step 8)
crate tag data/<slug>.classified.json
crate build-library data/<slug>.classified.json --target ~/Music/Library
crate build-event data/<slug>.classified.json --output ~/Music/Events/<EventName>/
```

The scan step can be skipped if the NAS library hasn't changed.

## Quality Checks

- [ ] All tracks from the source playlist are accounted for
- [ ] Classification reviewed and confirmed by user before proceeding
- [ ] Match rate is reasonable (>50% for a well-stocked library)
- [ ] Audio analysis completed for all matched tracks
- [ ] LLM tags assigned (energy, function, crowd, mood)
- [ ] Files are real copies (not symlinks) in the library and event folders
- [ ] Tags written successfully (genre, BPM, key, comment with structured tags)
- [ ] Missing tracks list provided to user for manual download
