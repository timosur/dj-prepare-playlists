---
name: sort-playlist-by-genre
description: 'Sort a Spotify wish playlist into genre-based sub-playlists for a DJ event. Use when: preparing a wedding or party set, organizing a messy wish playlist, splitting tracks by genre, creating event-specific sub-playlists from a source playlist. Requires: spotify MCP server connected.'
argument-hint: 'Provide the Spotify playlist URL or ID, event name, and event date'
---

# Sort Playlist by Genre

Split a raw Spotify wish playlist into organized genre-based sub-playlists for a specific event.

## When to Use

- A client sends a Spotify wish playlist for an upcoming event
- You need to organize random tracks into genre buckets for easy DJ navigation
- Preparing sub-playlists for a wedding, corporate party, or themed event

## Required MCP Servers

- **spotify** — must be connected and authenticated

## Input

The user provides:
- **Spotify playlist** — URL (e.g., `https://open.spotify.com/playlist/...`) or playlist ID
- **Event name** — e.g., "Wedding Schmidt"
- **Event date** — e.g., "2026-06-15"

## Procedure

### Step 1: Read the Source Playlist

1. Use `getPlaylistTracks` to fetch all tracks from the source playlist. Paginate if needed (100 tracks per call).
2. Report the total track count to the user.

### Step 2: Analyze Tracks

1. Collect all unique artist IDs from the tracks.
2. Use `getArtistsGenres` (batches of up to 50) to get genre tags for every artist.
3. Use `getTracksAudioFeatures` (batches of up to 100) to get BPM, energy, danceability, and key for every track.

### Step 3: Classify into Genre Buckets

Apply the mapping from [genre-buckets.md](./references/genre-buckets.md):

1. For each track, check its artist genre tags against the bucket definitions.
2. Use audio features as secondary signal (energy, BPM, danceability).
3. Use release year for era buckets (80s, 90s, 2000s) where applicable.
4. Tracks that don't fit → **Party Hits** (catch-all).
5. If any bucket has fewer than 3 tracks, merge it into the closest related bucket.

### Step 4: Present Classification to User

Before creating playlists, show the user a summary:

```
Source: "Wunschliste Schmidt" (87 tracks)

Proposed sub-playlists:
  Party Hits     — 23 tracks
  90s            — 15 tracks
  Schlager       — 12 tracks
  House / Dance  — 11 tracks
  Hip-Hop / R&B  — 9 tracks
  Rock / Indie   — 8 tracks
  Ballads / Slow — 5 tracks
  80s            — 4 tracks
```

Ask: *"Does this look right? Want me to move any tracks between categories or adjust the buckets?"*

Wait for user confirmation before proceeding.

### Step 5: Create Sub-Playlists

For each non-empty bucket:

1. Use `createPlaylist` with:
   - **Name**: `{Event Name} — {Bucket Name}` (e.g., "Wedding Schmidt — Party Hits")
   - **Description**: `{Event Name} — {Event Date} — {Bucket Name} — Auto-sorted from wish playlist`
2. Use `addTracksToPlaylist` to add the classified tracks.

### Step 6: Report Results

Show the user a summary of all created playlists with track counts and links.

## Quality Checks

- [ ] All tracks from the source playlist are accounted for (no tracks lost)
- [ ] No empty playlists created
- [ ] Bucket count is between 4-12 (manageable for DJing)
- [ ] User confirmed the classification before playlists were created
