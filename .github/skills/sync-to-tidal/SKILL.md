---
name: sync-to-tidal
description: 'Sync a Spotify playlist to Tidal by matching tracks via ISRC codes. Use when: copying a playlist from Spotify to Tidal, mirroring event playlists to the DJ platform, syncing master playlists cross-platform, transferring a wish playlist to Tidal. Requires: spotify and tidal MCP servers connected.'
argument-hint: 'Provide the Spotify playlist URL or ID to sync to Tidal'
---

# Sync Playlist to Tidal

Mirror a Spotify playlist to Tidal by matching tracks using ISRC codes. Creates a new Tidal playlist (or updates an existing one) with the matched tracks.

## When to Use

- After creating event sub-playlists on Spotify, sync them to Tidal for live DJing
- Syncing [DJ] master playlists to Tidal
- Any time a Spotify playlist needs a Tidal copy

## Required MCP Servers

- **spotify** — must be connected and authenticated
- **tidal** — must be connected and authenticated

## Input

The user provides:
- **Spotify playlist** — URL or playlist ID to sync
- **Tidal playlist name** (optional) — defaults to same name as Spotify playlist

## Procedure

### Step 1: Read Spotify Playlist

1. Use Spotify `getPlaylistTracks` to fetch all tracks. Paginate if needed.
2. Report playlist name and track count.

### Step 2: Collect ISRC Codes

ISRC codes are included in the `getPlaylistTracks` output (appended as `| ISRC: ...` to each track line). Parse them from the response.

- Tracks with ISRCs → ready for Tidal matching
- Tracks without ISRCs (local files, some regional releases) → mark as unresolvable

### Step 3: Check for Existing Tidal Playlist

1. Use Tidal `get_my_playlists` to list playlists.
2. Look for a playlist with the target name.
3. If found, ask the user: *"A Tidal playlist '{name}' already exists with {n} tracks. Should I update it (add missing tracks) or replace it (clear and re-add all)?"*
4. If not found, use Tidal `create_playlist` to create it.

### Step 4: Add Tracks to Tidal

1. Use Tidal `add_tracks_by_isrc` to add tracks using their ISRC codes.
2. This lets Tidal resolve each ISRC to its own catalog — ensuring the correct Tidal version of each track.
3. Process in batches to avoid rate limits.

### Step 5: Handle Failures

Track which ISRCs failed to resolve on Tidal. Common reasons:
- Track not available on Tidal
- Regional licensing differences
- Track is a local file on Spotify (no ISRC)

### Step 6: Report Results

```
Synced: "Wedding Schmidt — Party Hits" → Tidal

Results:
  ✓ 21/23 tracks matched and added
  ✗ 2 tracks not found on Tidal:
    - "Some Local Track" by Unknown Artist (no ISRC)
    - "Regional Release" by Artist X (ISRC: USRC12345678 — not on Tidal)
```

## Quality Checks

- [ ] All tracks with ISRCs were attempted
- [ ] Failed matches are reported with reason
- [ ] Tidal playlist name matches the Spotify source (or user's choice)
- [ ] No duplicate tracks added if updating an existing Tidal playlist
- [ ] User was asked before overwriting an existing Tidal playlist
