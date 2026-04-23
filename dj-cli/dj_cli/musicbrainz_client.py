"""MusicBrainz API client — fetch genre tags for tracks by ISRC."""

from __future__ import annotations

import time
from urllib.parse import quote

import requests

_BASE_URL = "https://musicbrainz.org/ws/2"
_HEADERS = {
    "User-Agent": "dj-cli/1.0.0 (https://github.com/timosur/dj-playlist-prepare)",
    "Accept": "application/json",
}

# MusicBrainz rate limit: 1 request per second
_MIN_REQUEST_INTERVAL = 1.1
_last_request_time = 0.0


def _rate_limited_get(url: str, params: dict | None = None) -> dict | None:
    """Make a rate-limited GET request to MusicBrainz."""
    global _last_request_time

    now = time.monotonic()
    wait = _MIN_REQUEST_INTERVAL - (now - _last_request_time)
    if wait > 0:
        time.sleep(wait)

    _last_request_time = time.monotonic()

    resp = requests.get(url, params=params, headers=_HEADERS, timeout=10)
    if resp.status_code == 503:
        # Rate limited — back off and retry once
        time.sleep(2)
        _last_request_time = time.monotonic()
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=10)

    if resp.status_code != 200:
        return None
    return resp.json()


def fetch_genres_by_isrc(isrc: str, min_votes: int = 2) -> tuple[list[str], int | None]:
    """Look up a recording by ISRC and return its genre/tag list and first release year.

    Only returns tags with at least min_votes to filter out community noise.
    Returns (genres, release_year) tuple.
    """
    url = f"{_BASE_URL}/recording"
    params = {"query": f"isrc:{isrc}", "fmt": "json", "limit": "1"}

    data = _rate_limited_get(url, params)
    if not data or not data.get("recordings"):
        return [], None

    recording = data["recordings"][0]

    # Extract genres
    tags = recording.get("tags", [])
    sorted_tags = sorted(tags, key=lambda t: t.get("count", 0), reverse=True)
    genres = [t["name"].lower() for t in sorted_tags if t.get("name") and t.get("count", 0) >= min_votes]

    # Extract first release year
    release_year = None
    date_str = recording.get("first-release-date", "")
    if date_str and len(date_str) >= 4:
        try:
            release_year = int(date_str[:4])
        except ValueError:
            pass

    return genres, release_year


def enrich_tracks_genres(tracks: list, progress_callback=None) -> int:
    """Enrich tracks that have no artist_genres with MusicBrainz tags.

    Also updates release_year and era from MusicBrainz first-release-date
    when available.
    Returns the number of tracks enriched.
    """
    enriched = 0
    candidates = [t for t in tracks if (not t.artist_genres or not t.release_year) and t.isrc]

    for i, track in enumerate(candidates):
        genres, mb_year = fetch_genres_by_isrc(track.isrc)
        updated = False
        if genres and not track.artist_genres:
            track.artist_genres = genres
            updated = True
        if mb_year:
            # Prefer MusicBrainz year — it reflects original release, not remaster
            track.release_year = mb_year
            track.era = track.compute_era()
            updated = True
        if updated:
            enriched += 1
        if progress_callback:
            progress_callback(i + 1, len(candidates), track, genres, mb_year)

    # Also compute era for any tracks that already have a year but no era
    for track in tracks:
        if track.release_year and not track.era:
            track.era = track.compute_era()

    return enriched
