"""MusicBrainz adapter — Protocol + live (1 rps via CLI client) + mock."""

from __future__ import annotations

from typing import Protocol


class MusicBrainzAdapter(Protocol):
    async def lookup_by_isrc(self, isrc: str) -> tuple[list[str], int | None]:
        """Return ``(genres, release_year)`` for a recording's ISRC.

        ``genres`` is a list of artist genre/tag strings. ``release_year`` is
        the first-release year as reported by MusicBrainz, or ``None``.
        """
        ...


class LiveMusicBrainzAdapter:
    """Real adapter — reuses cratekeeper.musicbrainz_client which enforces 1 req/sec."""

    async def lookup_by_isrc(self, isrc: str) -> tuple[list[str], int | None]:
        import asyncio

        from cratekeeper import musicbrainz_client as mbc

        fn = getattr(mbc, "fetch_genres_by_isrc", None)
        if fn is None:
            return [], None
        try:
            result = await asyncio.to_thread(fn, isrc)
        except Exception:
            return [], None
        if isinstance(result, tuple):
            genres, year = result
            return list(genres or []), year
        return list(result or []), None


class MockMusicBrainzAdapter:
    def __init__(self, mapping: dict[str, tuple[list[str], int | None]] | None = None) -> None:
        self._mapping = mapping or {}

    async def lookup_by_isrc(self, isrc: str) -> tuple[list[str], int | None]:
        entry = self._mapping.get(isrc)
        if entry is None:
            return [], None
        genres, year = entry
        return list(genres), year


def get_musicbrainz_adapter(use_mock: bool = False) -> MusicBrainzAdapter:
    return MockMusicBrainzAdapter() if use_mock else LiveMusicBrainzAdapter()
