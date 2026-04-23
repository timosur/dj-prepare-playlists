"""Mood analysis using essentia audio feature extraction.

Extracts BPM, energy, danceability from local audio files and maps
them to mood categories using genre-specific thresholds.

This module requires essentia to be installed (Linux: pip install essentia,
or use the provided Dockerfile).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dj_cli.mood_config import classify_mood


@dataclass
class AudioFeatures:
    """Extracted audio features for a single track."""

    bpm: float
    energy: float
    danceability: float
    loudness: float = 0.0  # in dB


def extract_features(file_path: str | Path) -> AudioFeatures:
    """Extract audio features from a local audio file using essentia.

    Raises ImportError if essentia is not installed.
    """
    try:
        import essentia
        import essentia.standard as es
    except ImportError:
        raise ImportError(
            "essentia is not installed. Use the Docker image or install on Linux:\n"
            "  pip install essentia\n"
            "Or run: docker compose run dj analyze-mood ..."
        )

    file_path = str(file_path)

    # Load audio (mono, 44100 Hz)
    loader = es.MonoLoader(filename=file_path, sampleRate=44100)
    audio = loader()

    # BPM detection
    rhythm_extractor = es.RhythmExtractor2013(method="multifeature")
    bpm, beats, beats_confidence, _, beats_intervals = rhythm_extractor(audio)

    # Energy (RMS-based, normalized to 0-1)
    rms = es.RMS()
    energy_values = []
    frame_generator = es.FrameGenerator(audio, frameSize=2048, hopSize=1024)
    for frame in frame_generator:
        energy_values.append(rms(frame))

    if energy_values:
        avg_rms = sum(energy_values) / len(energy_values)
        # Normalize RMS to roughly 0-1 range (typical RMS for music: 0.01 - 0.3)
        energy = min(1.0, avg_rms / 0.2)
    else:
        energy = 0.0

    # Danceability
    danceability_extractor = es.Danceability()
    danceability, _ = danceability_extractor(audio)

    # Loudness (integrated)
    loudness_extractor = es.LoudnessEBUR128(sampleRate=44100)
    try:
        # Needs stereo input, reload as stereo
        stereo_loader = es.AudioLoader(filename=file_path)
        stereo_audio, sr, channels, md5, bit_rate, codec = stereo_loader()
        momentary, short_term, integrated, loudness_range = loudness_extractor(stereo_audio)
    except Exception:
        integrated = -14.0  # reasonable default

    return AudioFeatures(
        bpm=round(bpm, 1),
        energy=round(energy, 3),
        danceability=round(danceability, 3),
        loudness=round(integrated, 1),
    )


def analyze_track(file_path: str | Path, genre: str | None = None) -> tuple[AudioFeatures, str]:
    """Extract features and classify mood for a single track.

    Returns (features, mood_name).
    """
    features = extract_features(file_path)
    mood = classify_mood(features.bpm, features.energy, features.danceability, genre)
    return features, mood


def analyze_tracks(tracks: list, progress_callback=None) -> int:
    """Analyze mood for tracks that have a local_path set.

    Mutates tracks: sets mood field.
    Returns number of tracks analyzed.
    """
    candidates = [t for t in tracks if t.local_path and Path(t.local_path).exists()]
    analyzed = 0

    for i, track in enumerate(candidates):
        try:
            features, mood = analyze_track(track.local_path, genre=track.bucket)
            track.mood = mood
            analyzed += 1
        except Exception as e:
            track.mood = None
            if progress_callback:
                progress_callback(i + 1, len(candidates), track, None, str(e))
            continue

        if progress_callback:
            progress_callback(i + 1, len(candidates), track, mood, None)

    return analyzed
