# Genre Bucket Mapping

Default genre buckets for DJ playlist sorting. These are broad categories designed to keep the number of playlists manageable (~10-12) while covering common wedding/event music.

## Standard Buckets

| Bucket Name | Spotify Genre Tags (partial matches) | Audio Feature Hints |
|---|---|---|
| **80s** | 80s, new wave, synthpop, 80s pop, 80s rock | year 1980-1989 |
| **90s** | 90s, 90s pop, 90s rock, 90s hip hop, eurodance | year 1990-1999 |
| **2000s** | 2000s, 2000s pop | year 2000-2009 |
| **Party Hits** | pop, dance pop, europop, party, viral pop, german pop | high energy (>0.7), high danceability (>0.7) |
| **Schlager** | schlager, german schlager, discofox, volksmusik, german pop | — |
| **Hip-Hop / R&B** | hip hop, rap, r&b, trap, urban contemporary, german hip hop | — |
| **Rock / Indie** | rock, indie, alternative, punk, classic rock, indie pop | — |
| **House / Dance** | house, deep house, dance, edm, electro house, tropical house | BPM 120-130 |
| **Techno / Trance** | techno, trance, hardstyle, hard techno, psytrance | BPM 130-150+ |
| **Oldschool** | disco, funk, soul, motown, classic soul, boogie | year before 1980 |
| **Latin / Reggaeton** | reggaeton, latin, salsa, bachata, latin pop | — |
| **Ballads / Slow** | ballad, slow, acoustic, singer-songwriter | low energy (<0.4), low tempo (<100 BPM) |

## Matching Rules

1. **Primary**: Match against Spotify artist genre tags (use `getArtistsGenres` tool). A partial/substring match is sufficient.
2. **Secondary**: Use audio features (`getTracksAudioFeatures`) for energy, danceability, BPM to break ties or confirm classification.
3. **Era override**: If a track's release year clearly places it in a decade bucket (80s, 90s, 2000s), that takes priority over genre — unless the genre is very specific (e.g., Schlager stays Schlager regardless of era).
4. **Fallback**: Tracks that don't clearly fit any bucket go into **Party Hits** as the catch-all.
5. **Consolidation**: If a bucket would contain fewer than 3 tracks, merge it into the closest related bucket.

## Customization

These buckets can be adjusted per event. For example:
- A techno-heavy event might split **Techno / Trance** into separate buckets
- A German-focused event might add a **Deutsche Hits** bucket
- A 90s-themed party might split 90s into sub-genres

The AI agent should suggest adjustments based on the playlist content before creating sub-playlists.
