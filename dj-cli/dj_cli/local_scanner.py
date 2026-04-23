"""Scan a local directory for audio files and index metadata into SQLite."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4

AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".aiff", ".aif", ".m4a", ".ogg", ".opus"}

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "local-library.db"


def _init_db(db_path: Path) -> sqlite3.Connection:
    """Create/open the SQLite database with the tracks table."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tracks (
            path TEXT PRIMARY KEY,
            title TEXT,
            artist TEXT,
            album TEXT,
            isrc TEXT,
            year INTEGER,
            duration_ms INTEGER,
            format TEXT,
            title_norm TEXT,
            artist_norm TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_isrc ON tracks(isrc) WHERE isrc IS NOT NULL")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_artist_title ON tracks(artist_norm, title_norm)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scan_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    return conn


def _normalize_for_index(text: str | None) -> str | None:
    """Simple normalization for index lookups."""
    if not text:
        return None
    import re
    import unicodedata
    text = text.lower().strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_metadata(file_path: Path) -> dict | None:
    """Extract metadata from a single audio file using mutagen.

    Returns a dict suitable for SQLite insertion, or None on failure.
    """
    try:
        audio = mutagen.File(str(file_path), easy=True)
    except Exception:
        return None

    title = None
    artist = None
    album = None
    isrc = None
    year = None
    duration_ms = 0

    if audio is None:
        return {
            "path": str(file_path),
            "title": None, "artist": None, "album": None,
            "isrc": None, "year": None, "duration_ms": 0,
            "format": file_path.suffix.lstrip(".").lower(),
            "title_norm": None, "artist_norm": None,
        }

    # Duration
    if audio.info and hasattr(audio.info, "length"):
        duration_ms = int(audio.info.length * 1000)

    if isinstance(audio, (MP3, FLAC)) or hasattr(audio, "tags"):
        tags = audio
        if isinstance(audio, MP3):
            try:
                tags = EasyID3(str(file_path))
            except Exception:
                tags = audio

        title = _first_tag(tags, "title")
        artist = _first_tag(tags, "artist")
        album = _first_tag(tags, "album")
        isrc = _first_tag(tags, "isrc")

        date_str = _first_tag(tags, "date") or _first_tag(tags, "year")
        if date_str:
            try:
                year = int(date_str[:4])
            except (ValueError, IndexError):
                pass

    if isinstance(audio, MP4):
        mp4_tags = audio.tags or {}
        title = _first_mp4_tag(mp4_tags, "\xa9nam")
        artist = _first_mp4_tag(mp4_tags, "\xa9ART")
        album = _first_mp4_tag(mp4_tags, "\xa9alb")
        date_str = _first_mp4_tag(mp4_tags, "\xa9day")
        if date_str:
            try:
                year = int(date_str[:4])
            except (ValueError, IndexError):
                pass

    return {
        "path": str(file_path),
        "title": title, "artist": artist, "album": album,
        "isrc": isrc.upper() if isrc else None,
        "year": year, "duration_ms": duration_ms,
        "format": file_path.suffix.lstrip(".").lower(),
        "title_norm": _normalize_for_index(title),
        "artist_norm": _normalize_for_index(artist),
    }


def _first_tag(tags, key: str) -> str | None:
    """Get first value for a tag key, or None."""
    try:
        val = tags.get(key)
        if val:
            return val[0] if isinstance(val, list) else str(val)
    except Exception:
        pass
    return None


def _first_mp4_tag(tags: dict, key: str) -> str | None:
    """Get first value for an MP4 tag key, or None."""
    val = tags.get(key)
    if val:
        return str(val[0]) if isinstance(val, list) else str(val)
    return None


def scan_directory(
    root: Path,
    db_path: Path = DEFAULT_DB_PATH,
    incremental: bool = True,
    progress_callback=None,
) -> tuple[sqlite3.Connection, int, int]:
    """Recursively scan a directory for audio files and index into SQLite.

    Args:
        root: Directory to scan.
        db_path: Path to SQLite database.
        incremental: If True, skip files already in the DB.
        progress_callback: Called with (new_count, skipped, file_path).

    Returns (connection, new_count, skipped_count).
    """
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Directory not found: {root}")

    conn = _init_db(db_path)

    # Get existing paths for incremental scan
    existing_paths: set[str] = set()
    if incremental:
        cursor = conn.execute("SELECT path FROM tracks")
        existing_paths = {row[0] for row in cursor}

    new_count = 0
    skipped = 0
    batch: list[dict] = []
    batch_size = 500

    # Use os.walk — much faster than rglob over NAS/SMB (avoids per-file stat)
    for dirpath, _dirnames, filenames in os.walk(root):
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in AUDIO_EXTENSIONS:
                continue

            file_path = Path(dirpath) / fname

            if str(file_path) in existing_paths:
                skipped += 1
                if progress_callback and skipped % 500 == 0:
                    progress_callback(new_count, skipped, file_path)
                continue

            meta = _extract_metadata(file_path)
            if meta:
                batch.append(meta)
                new_count += 1

            if len(batch) >= batch_size:
                _insert_batch(conn, batch)
                batch.clear()

            if progress_callback and (new_count + skipped) % 50 == 0:
                progress_callback(new_count, skipped, file_path)

    # Final batch
    if batch:
        _insert_batch(conn, batch)

    # Final progress
    if progress_callback:
        progress_callback(new_count, skipped, None)

    # Update scan metadata
    conn.execute(
        "INSERT OR REPLACE INTO scan_meta (key, value) VALUES (?, ?)",
        ("last_scan", datetime.now(timezone.utc).isoformat()),
    )
    conn.execute(
        "INSERT OR REPLACE INTO scan_meta (key, value) VALUES (?, ?)",
        ("root_path", str(root)),
    )
    conn.commit()

    return conn, new_count, skipped


def _insert_batch(conn: sqlite3.Connection, batch: list[dict]) -> None:
    """Insert a batch of track records into the database."""
    conn.executemany(
        """INSERT OR REPLACE INTO tracks
           (path, title, artist, album, isrc, year, duration_ms, format, title_norm, artist_norm)
           VALUES (:path, :title, :artist, :album, :isrc, :year, :duration_ms, :format, :title_norm, :artist_norm)""",
        batch,
    )
    conn.commit()


def get_db_stats(db_path: Path = DEFAULT_DB_PATH) -> dict:
    """Get summary stats from the library database."""
    if not db_path.exists():
        return {"total": 0}
    conn = sqlite3.connect(str(db_path))
    total = conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
    with_tags = conn.execute("SELECT COUNT(*) FROM tracks WHERE title IS NOT NULL AND artist IS NOT NULL").fetchone()[0]
    with_isrc = conn.execute("SELECT COUNT(*) FROM tracks WHERE isrc IS NOT NULL").fetchone()[0]

    formats = {}
    for row in conn.execute("SELECT format, COUNT(*) FROM tracks GROUP BY format ORDER BY COUNT(*) DESC"):
        formats[row[0]] = row[1]

    last_scan = None
    row = conn.execute("SELECT value FROM scan_meta WHERE key='last_scan'").fetchone()
    if row:
        last_scan = row[0]

    conn.close()
    return {
        "total": total, "with_tags": with_tags, "with_isrc": with_isrc,
        "formats": formats, "last_scan": last_scan,
    }
