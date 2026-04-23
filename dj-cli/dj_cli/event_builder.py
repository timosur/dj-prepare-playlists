"""Build event-specific folders by copying files from the master library."""

from __future__ import annotations

import shutil
from pathlib import Path

from dj_cli.models import Track


def _safe_filename(name: str) -> str:
    """Sanitize a string for use as a filename."""
    # Replace problematic characters
    for ch in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
        name = name.replace(ch, '-')
    return name.strip('. ')


def _track_filename(track: Track) -> str:
    """Build a filename from track metadata: Artist - Title.ext"""
    artist = ", ".join(track.artists) if track.artists else "Unknown"
    title = track.name or "Unknown"
    return _safe_filename(f"{artist} - {title}")


def build_event_folder(
    tracks: list[Track],
    output_dir: Path,
    progress_callback=None,
) -> tuple[int, int, list[Track]]:
    """Create an event folder with Genre/Mood/ structure by copying files.

    Returns (created_count, skipped_count, missing_tracks).
    """
    output_dir = Path(output_dir)
    created = 0
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

        # Build target path: output_dir / Genre / Mood / Artist - Title.ext
        genre = _safe_filename(track.bucket or "Unsorted")
        mood = _safe_filename(track.mood or "Unclassified")
        filename = _track_filename(track) + source.suffix

        target_dir = output_dir / genre / mood
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / filename

        if target_path.exists():
            skipped += 1
        else:
            shutil.copy2(str(source), str(target_path))
            created += 1

        if progress_callback:
            progress_callback(i + 1, len(tracks), track, target_path)

    # Write missing report
    if missing:
        missing_file = output_dir / "_missing.txt"
        lines = [f"{t.display_name()} (ISRC: {t.isrc or 'none'})" for t in missing]
        missing_file.write_text("\n".join(lines))

    return created, skipped, missing
