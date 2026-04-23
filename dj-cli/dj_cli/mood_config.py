"""Genre-specific mood thresholds for DJ classification.

Moods are determined by audio features (BPM, energy, danceability, etc.)
with thresholds that vary by genre — e.g., "Chill" Techno is faster than "Chill" Pop.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MoodThresholds:
    """Thresholds for a single mood level within a genre."""

    name: str
    min_bpm: float = 0
    max_bpm: float = 999
    min_energy: float = 0
    max_energy: float = 1.0
    min_danceability: float = 0
    max_danceability: float = 1.0


# Ordered from low to high energy within each genre.
# The classifier tries thresholds top-to-bottom; first match wins.
MOOD_PROFILES: dict[str, list[MoodThresholds]] = {
    "Techno / Melodic": [
        MoodThresholds("Chill", max_bpm=122, max_energy=0.45),
        MoodThresholds("Warm-Up", min_bpm=118, max_bpm=128, min_energy=0.3, max_energy=0.6),
        MoodThresholds("Groovy", min_bpm=124, max_bpm=134, min_energy=0.5, max_energy=0.75),
        MoodThresholds("Energetic", min_bpm=130, max_bpm=142, min_energy=0.65),
        MoodThresholds("Peak", min_bpm=138, min_energy=0.8),
    ],
    "House / Dance": [
        MoodThresholds("Chill", max_bpm=118, max_energy=0.4),
        MoodThresholds("Warm-Up", min_bpm=115, max_bpm=124, min_energy=0.3, max_energy=0.6),
        MoodThresholds("Groovy", min_bpm=120, max_bpm=128, min_energy=0.45, max_energy=0.75),
        MoodThresholds("Energetic", min_bpm=124, max_bpm=134, min_energy=0.6),
        MoodThresholds("Peak", min_bpm=128, min_energy=0.78),
    ],
    "Drum & Bass": [
        MoodThresholds("Chill", max_bpm=168, max_energy=0.45),
        MoodThresholds("Groovy", min_bpm=165, max_bpm=176, min_energy=0.4, max_energy=0.7),
        MoodThresholds("Energetic", min_bpm=172, max_bpm=180, min_energy=0.6),
        MoodThresholds("Peak", min_bpm=174, min_energy=0.8),
    ],
    "Rock / Indie": [
        MoodThresholds("Chill", max_bpm=105, max_energy=0.4),
        MoodThresholds("Warm-Up", min_bpm=95, max_bpm=120, min_energy=0.3, max_energy=0.6),
        MoodThresholds("Groovy", min_bpm=110, max_bpm=135, min_energy=0.45, max_energy=0.75),
        MoodThresholds("Energetic", min_bpm=125, min_energy=0.65),
        MoodThresholds("Peak", min_bpm=140, min_energy=0.8),
    ],
    "Hip-Hop / R&B": [
        MoodThresholds("Chill", max_bpm=90, max_energy=0.35),
        MoodThresholds("Groovy", min_bpm=80, max_bpm=110, min_energy=0.3, max_energy=0.65),
        MoodThresholds("Energetic", min_bpm=100, min_energy=0.6),
        MoodThresholds("Peak", min_bpm=120, min_energy=0.75),
    ],
    "Latin / Reggaeton": [
        MoodThresholds("Chill", max_bpm=95, max_energy=0.4),
        MoodThresholds("Groovy", min_bpm=88, max_bpm=105, min_energy=0.35, max_energy=0.7),
        MoodThresholds("Energetic", min_bpm=95, min_energy=0.6),
        MoodThresholds("Peak", min_bpm=110, min_energy=0.78),
    ],
    "Schlager": [
        MoodThresholds("Chill", max_bpm=110, max_energy=0.4),
        MoodThresholds("Groovy", min_bpm=105, max_bpm=135, min_energy=0.35, max_energy=0.7),
        MoodThresholds("Energetic", min_bpm=125, min_energy=0.6),
        MoodThresholds("Peak", min_bpm=140, min_energy=0.75),
    ],
}

# Default thresholds for genres without a specific profile
DEFAULT_MOODS: list[MoodThresholds] = [
    MoodThresholds("Chill", max_bpm=105, max_energy=0.35),
    MoodThresholds("Warm-Up", min_bpm=95, max_bpm=120, min_energy=0.25, max_energy=0.55),
    MoodThresholds("Groovy", min_bpm=110, max_bpm=135, min_energy=0.4, max_energy=0.7),
    MoodThresholds("Energetic", min_bpm=120, min_energy=0.6),
    MoodThresholds("Peak", min_bpm=135, min_energy=0.8),
]

# Romantic override: low energy + low danceability regardless of genre
ROMANTIC_THRESHOLD = MoodThresholds("Romantic", max_bpm=110, max_energy=0.3, max_danceability=0.4)


def classify_mood(bpm: float, energy: float, danceability: float, genre: str | None = None) -> str:
    """Classify a track's mood based on audio features and genre context."""
    # Check romantic first (cross-genre)
    rt = ROMANTIC_THRESHOLD
    if (bpm <= rt.max_bpm and energy <= rt.max_energy and danceability <= rt.max_danceability):
        return "Romantic"

    # Get genre-specific or default thresholds
    thresholds = MOOD_PROFILES.get(genre or "", DEFAULT_MOODS)

    # Try from highest energy to lowest (reverse order = Peak first)
    for mood in reversed(thresholds):
        if (mood.min_bpm <= bpm <= mood.max_bpm
                and mood.min_energy <= energy <= mood.max_energy
                and mood.min_danceability <= danceability <= mood.max_danceability):
            return mood.name

    # Fallback: use energy to pick the closest mood
    if energy >= 0.7:
        return "Energetic"
    elif energy >= 0.45:
        return "Groovy"
    elif energy >= 0.25:
        return "Warm-Up"
    return "Chill"
