"""Build a master library by copying files into Genre/Mood/ folder structure."""

from __future__ import annotations

import shutil
from pathlib import Path

from dj_cli.models import Track


def _safe_filename(name: str) -> str:
    """Sanitize a string for use as a filename."""
    for ch in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
        name = name.replace(ch, '-')
    return name.strip('. ')


def _track_filename(track: Track) -> str:
    """Build a filename from track metadata: Artist - Title.ext"""
    artist = ", ".join(track.artists) if track.artists else "Unknown"
    title = track.name or "Unknown"
    return _safe_filename(f"{artist} - {title}")


def build_library(
    tracks: list[Track],
    target_dir: Path,
    progress_callback=None,
) -> tuple[int, int, list[Track]]:
    """Copy matched local files into Genre/Mood/ structure in the target directory.

    Only processes tracks that have a local_path and a mood set.
    Returns (copied_count, skipped_count, missing_tracks).
    """
    target_dir = Path(target_dir)
    copied = 0
    skipped = 0
    missing: list[Track] = []

    for i, track in enumerate(tracks):
        if not track.local_path:
            missing.append(track)
            continue

        source = Path(track.local_path)
        if not source.exists():
            missing.append(track)
            continue

        # Build target path: target_dir / Genre / Mood / Artist - Title.ext
        genre = _safe_filename(track.bucket or "Unsorted")
        mood = _safe_filename(track.mood or "Unclassified")
        filename = _track_filename(track) + source.suffix

        dest_dir = target_dir / genre / mood
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / filename

        if dest_path.exists():
            skipped += 1
        else:
            shutil.copy2(str(source), str(dest_path))
            copied += 1

        # Update local_path to point to the new location
        track.local_path = str(dest_path)

        if progress_callback:
            progress_callback(i + 1, len(tracks), track, dest_path)

    return copied, skipped, missing
