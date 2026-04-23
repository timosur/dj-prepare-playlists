"""Match Spotify tracks to local audio files using SQLite-backed lookups."""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from pathlib import Path

from thefuzz import fuzz

from dj_cli.local_scanner import DEFAULT_DB_PATH
from dj_cli.models import Track


def _normalize(text: str) -> str:
    """Normalize a string for comparison: lowercase, strip accents, remove punctuation."""
    text = text.lower().strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    # Remove common suffixes that differ between platforms
    text = re.sub(r"\s*[-–—]\s*(radio\s*(edit|mix|version)|remaster(ed)?(\s*\d{4})?|single\s*version|original\s*mix|feat\.?\s*.+)$", "", text, flags=re.IGNORECASE)
    # Remove parenthesized suffixes
    text = re.sub(r"\s*\(.*?\)\s*$", "", text)
    # Remove punctuation
    text = re.sub(r"[^\w\s]", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_artist(text: str) -> str:
    """Normalize artist name for comparison."""
    text = _normalize(text)
    text = re.sub(r"^the\s+", "", text)
    return text


class MatchResult:
    """Result of matching a single Track to a local file."""

    def __init__(self, track: Track, local_path: str | None, method: str, score: int):
        self.track = track
        self.local_path = local_path
        self.method = method  # "isrc", "exact", "fuzzy", "none"
        self.score = score


def match_tracks(
    tracks: list[Track],
    db_path: Path = DEFAULT_DB_PATH,
    fuzzy_threshold: int = 85,
    progress_callback=None,
) -> list[MatchResult]:
    """Match Spotify tracks to local files using SQLite-backed lookups.

    Strategy order:
    1. ISRC exact match (indexed query)
    2. Artist + Title exact match (normalized, indexed query)
    3. Fuzzy match on Artist + Title (loads candidates lazily)
    4. Unmatched
    """
    conn = sqlite3.connect(str(db_path))
    matched_paths: set[str] = set()
    results: list[MatchResult] = []

    for i, track in enumerate(tracks):
        result = _match_single(track, conn, fuzzy_threshold, matched_paths)
        results.append(result)
        if result.local_path:
            matched_paths.add(result.local_path)
            track.local_path = result.local_path
        if progress_callback:
            progress_callback(i + 1, len(tracks), track, result)

    conn.close()
    return results


def _match_single(
    track: Track,
    conn: sqlite3.Connection,
    fuzzy_threshold: int,
    matched_paths: set[str],
) -> MatchResult:
    """Try to match a single track using all strategies."""

    # Strategy 1: ISRC (fast indexed lookup)
    if track.isrc:
        row = conn.execute(
            "SELECT path FROM tracks WHERE isrc = ? LIMIT 1",
            (track.isrc.upper(),),
        ).fetchone()
        if row and row[0] not in matched_paths:
            return MatchResult(track, row[0], "isrc", 100)

    # Strategy 2: Exact artist + title (normalized, indexed)
    title_norm = _normalize(track.name)
    for artist in track.artists:
        artist_norm = _normalize_artist(artist)
        row = conn.execute(
            "SELECT path FROM tracks WHERE artist_norm = ? AND title_norm = ? LIMIT 1",
            (artist_norm, title_norm),
        ).fetchone()
        if row and row[0] not in matched_paths:
            return MatchResult(track, row[0], "exact", 100)

    # Strategy 3: Fuzzy match — query candidates with same first letter of artist
    query = f"{_normalize_artist(track.artists[0])} {_normalize(track.name)}"
    artist_prefix = _normalize_artist(track.artists[0])[:3]
    if artist_prefix:
        candidates = conn.execute(
            "SELECT path, artist_norm, title_norm FROM tracks WHERE artist_norm LIKE ? AND title_norm IS NOT NULL",
            (artist_prefix + "%",),
        ).fetchall()

        best_score = 0
        best_path = None
        for path, a_norm, t_norm in candidates:
            if path in matched_paths or not a_norm or not t_norm:
                continue
            candidate_str = f"{a_norm} {t_norm}"
            score = fuzz.token_sort_ratio(query, candidate_str)
            if score > best_score:
                best_score = score
                best_path = path

        if best_path and best_score >= fuzzy_threshold:
            return MatchResult(track, best_path, "fuzzy", best_score)

    return MatchResult(track, None, "none", 0)
