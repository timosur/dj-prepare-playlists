"""Spotify adapter — Protocol + live client (delegates to cratekeeper-cli) + mock."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class SpotifyTrackData:
    id: str
    name: str
    artists: list[str]
    artist_ids: list[str]
    album: str | None
    duration_ms: int
    isrc: str | None = None
    release_year: int | None = None
    artist_genres: list[str] = field(default_factory=list)


class SpotifyAdapter(Protocol):
    def fetch_playlist(self, playlist_url_or_id: str) -> tuple[str, str, list[SpotifyTrackData]]:
        """Return (playlist_id, playlist_name, tracks)."""
        ...


# --------------------------------------------------------------------------- live


class LiveSpotifyAdapter:
    """Real adapter — uses spotipy via cratekeeper.spotify_client.

    Reuses the existing `spotify-mcp/spotify-config.json` for OAuth tokens.
    Token refresh is handled inside `get_spotify_client()`.
    """

    def fetch_playlist(self, playlist_url_or_id: str) -> tuple[str, str, list[SpotifyTrackData]]:
        from cratekeeper.spotify_client import (
            extract_playlist_id,
            fetch_artist_genres,
            fetch_playlist_tracks,
            get_spotify_client,
        )

        sp = get_spotify_client()
        pid = extract_playlist_id(playlist_url_or_id)
        name, tracks = fetch_playlist_tracks(sp, pid)

        all_artist_ids = sorted({aid for t in tracks for aid in t.artist_ids})
        genres_by_artist = fetch_artist_genres(sp, all_artist_ids) if all_artist_ids else {}

        out: list[SpotifyTrackData] = []
        for t in tracks:
            merged: list[str] = []
            seen: set[str] = set()
            for aid in t.artist_ids:
                for g in genres_by_artist.get(aid, []):
                    if g not in seen:
                        merged.append(g)
                        seen.add(g)
            out.append(
                SpotifyTrackData(
                    id=t.id,
                    name=t.name,
                    artists=list(t.artists),
                    artist_ids=list(t.artist_ids),
                    album=t.album,
                    duration_ms=t.duration_ms,
                    isrc=t.isrc,
                    release_year=t.release_year,
                    artist_genres=merged,
                )
            )
        return pid, name, out


# --------------------------------------------------------------------------- mock


class MockSpotifyAdapter:
    """Deterministic in-memory Spotify for tests + offline development."""

    def __init__(self, fixtures: dict[str, tuple[str, list[SpotifyTrackData]]] | None = None) -> None:
        self._fixtures = fixtures or _DEFAULT_FIXTURE

    def fetch_playlist(self, playlist_url_or_id: str) -> tuple[str, str, list[SpotifyTrackData]]:
        pid = playlist_url_or_id.rsplit("/", 1)[-1].split("?", 1)[0]
        if pid not in self._fixtures:
            raise KeyError(f"unknown playlist {pid}")
        name, tracks = self._fixtures[pid]
        return pid, name, list(tracks)


def _t(i: int, name: str, artists: list[str], genres: list[str], year: int, isrc: str | None = None) -> SpotifyTrackData:
    return SpotifyTrackData(
        id=f"sp_{i:03d}",
        name=name,
        artists=artists,
        artist_ids=[f"art_{a.lower().replace(' ', '_')}" for a in artists],
        album=f"Album {i}",
        duration_ms=210_000,
        isrc=isrc,
        release_year=year,
        artist_genres=genres,
    )


_DEFAULT_FIXTURE: dict[str, tuple[str, list[SpotifyTrackData]]] = {
    "test_wedding": (
        "Test Wedding Wishlist",
        [
            _t(1, "Mr. Brightside", ["The Killers"], ["alternative rock", "indie rock"], 2003, "USIR20300172"),
            _t(2, "Get Lucky", ["Daft Punk", "Pharrell Williams"], ["french house", "house"], 2013, "GBARL1300041"),
            _t(3, "Atemlos durch die Nacht", ["Helene Fischer"], ["schlager"], 2013),
            _t(4, "One More Time", ["Daft Punk"], ["french house", "house"], 2000),
            _t(5, "Strobe", ["deadmau5"], ["progressive house", "electro house"], 2009),
            _t(6, "I Wanna Dance with Somebody", ["Whitney Houston"], ["pop", "r&b"], 1987, "USAR18700100"),
            _t(7, "Take On Me", ["a-ha"], ["synthpop", "new wave"], 1985),
            _t(8, "Levels", ["Avicii"], ["edm", "big room"], 2011),
            _t(9, "Around the World", ["ATC"], ["dance", "eurodance"], 2000),
            _t(10, "Wonderwall", ["Oasis"], ["britpop", "alternative rock"], 1995),
        ],
    ),
}


def get_spotify_adapter(use_mock: bool = False) -> SpotifyAdapter:
    """Factory — pass `use_mock=True` for tests / offline."""
    return MockSpotifyAdapter() if use_mock else LiveSpotifyAdapter()
