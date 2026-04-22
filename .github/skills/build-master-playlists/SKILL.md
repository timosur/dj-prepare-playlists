---
name: build-master-playlists
description: 'Add tracks from a Spotify wish playlist or event sub-playlists into cross-event [DJ] master playlists organized by genre. Use when: building a DJ library, adding new event tracks to master genre playlists, maintaining cross-wedding genre collections, populating [DJ] playlists. Requires: spotify MCP server connected.'
argument-hint: 'Provide the Spotify playlist URL or ID containing tracks to add to master playlists'
---

# Build Master Playlists

Add tracks from a source playlist into cross-event **[DJ] master playlists** — one per genre bucket. These master playlists grow over time and serve as the DJ's central library.

## When to Use

- After processing a new event wish playlist
- When you want to add tracks to the central genre library
- When building up master playlists from multiple events
- After running `sort-playlist-by-genre` and wanting to also populate the masters

## Required MCP Servers

- **spotify** — must be connected and authenticated

## Input

The user provides:
- **Spotify playlist(s)** — one or more playlist URLs/IDs to process (can be a raw wish list or already-sorted sub-playlists)

## Procedure

### Step 1: Read Source Tracks

1. Use `getPlaylistTracks` to fetch all tracks from the source playlist(s). Paginate if needed.
2. Report total track count.

### Step 2: Analyze & Classify

1. Collect unique artist IDs, fetch genres via `getArtistsGenres` (batches of 50).
2. Fetch audio features via `getTracksAudioFeatures` (batches of 100).
3. Classify each track into a genre bucket using [genre-buckets.md](./references/genre-buckets.md).

### Step 3: Find or Create Master Playlists

1. Use `getMyPlaylists` to list all existing playlists.
2. For each genre bucket that has tracks, look for an existing playlist named **`[DJ] {Bucket Name}`**.
3. If it doesn't exist, use `createPlaylist` to create it:
   - **Name**: `[DJ] {Bucket Name}` (e.g., `[DJ] Party Hits`)
   - **Description**: `Cross-event master playlist — {Bucket Name}`

### Step 4: Check for Duplicates

For each master playlist that will receive tracks:

1. Use `getPlaylistTracks` to fetch the existing tracks in the master playlist.
2. Compare track IDs with the tracks to be added.
3. Separate into **new tracks** (to add) and **duplicates** (to skip).

### Step 5: Add Tracks

1. Use `addTracksToPlaylist` to add only the new (non-duplicate) tracks to each master playlist.

### Step 6: Report Results

Present a summary:

```
Master Playlist Updates:
  [DJ] Party Hits     — +12 new tracks (3 duplicates skipped), total: 87
  [DJ] 90s            — +8 new tracks (1 duplicate skipped), total: 45
  [DJ] Schlager       — +5 new tracks, total: 32
  [DJ] House / Dance  — +4 new tracks, total: 28
  [DJ] Hip-Hop / R&B  — created new, 6 tracks
  
Skipped duplicates (already in master):
  - "Macarena" by Los del Rio → [DJ] Party Hits
  - "Everybody" by Backstreet Boys → [DJ] 90s
  ...
```

## Quality Checks

- [ ] All source tracks classified into exactly one bucket
- [ ] No duplicates added to master playlists
- [ ] Duplicates reported to user
- [ ] New master playlists follow `[DJ] {Name}` convention
- [ ] Bucket count stays manageable (merge small buckets)
