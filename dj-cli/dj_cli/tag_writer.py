"""Write genre, mood, and era metadata into audio file ID3/FLAC tags."""

from __future__ import annotations

from pathlib import Path

import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.id3 import ID3, TCON, COMM, TIT1, GRP1
from mutagen.mp3 import MP3

from dj_cli.models import Track


def _compute_era(year: int | None) -> str | None:
    """Derive era label from release year."""
    if not year:
        return None
    decade = (year // 10) * 10
    if decade <= 1970:
        return "Oldschool"
    return f"{decade}s"


def tag_track(track: Track) -> bool:
    """Write classification metadata into a track's audio file tags.

    Sets: Genre (bucket), Grouping (mood), Content Group (era),
    Comment (classification source).

    Returns True if tags were written successfully.
    """
    if not track.local_path:
        return False

    path = Path(track.local_path)
    if not path.exists():
        return False

    suffix = path.suffix.lower()

    try:
        if suffix == ".mp3":
            return _tag_mp3(path, track)
        elif suffix == ".flac":
            return _tag_flac(path, track)
        else:
            # For other formats, try generic mutagen
            return _tag_generic(path, track)
    except Exception:
        return False


def _tag_mp3(path: Path, track: Track) -> bool:
    """Write tags to an MP3 file using ID3."""
    try:
        tags = ID3(str(path))
    except mutagen.id3.ID3NoHeaderError:
        tags = ID3()

    # Genre (TCON)
    if track.bucket:
        tags.delall("TCON")
        tags.add(TCON(encoding=3, text=[track.bucket]))

    # Grouping / Mood (GRP1 = iTunes grouping, TIT1 = content group)
    if track.mood:
        tags.delall("GRP1")
        tags.add(GRP1(encoding=3, text=[track.mood]))
        tags.delall("TIT1")
        tags.add(TIT1(encoding=3, text=[track.mood]))

    # Era in comment
    era = _compute_era(track.release_year)
    if era:
        track.era = era
        tags.delall("COMM")
        tags.add(COMM(encoding=3, lang="eng", desc="era", text=[era]))

    tags.save(str(path))
    return True


def _tag_flac(path: Path, track: Track) -> bool:
    """Write tags to a FLAC file."""
    audio = FLAC(str(path))

    if track.bucket:
        audio["genre"] = track.bucket
    if track.mood:
        audio["grouping"] = track.mood
        audio["mood"] = track.mood

    era = _compute_era(track.release_year)
    if era:
        track.era = era
        audio["era"] = era
        audio["comment"] = f"Era: {era}"

    audio.save()
    return True


def _tag_generic(path: Path, track: Track) -> bool:
    """Try to write tags using mutagen's easy interface."""
    audio = mutagen.File(str(path), easy=True)
    if audio is None:
        return False

    if track.bucket:
        audio["genre"] = track.bucket

    era = _compute_era(track.release_year)
    if era:
        track.era = era

    audio.save()
    return True


def tag_tracks(tracks: list[Track], progress_callback=None) -> tuple[int, int]:
    """Write tags for all tracks with a local_path.

    Returns (success_count, fail_count).
    """
    candidates = [t for t in tracks if t.local_path]
    success = 0
    failed = 0

    for i, track in enumerate(candidates):
        ok = tag_track(track)
        if ok:
            success += 1
        else:
            failed += 1
        if progress_callback:
            progress_callback(i + 1, len(candidates), track, ok)

    return success, failed
