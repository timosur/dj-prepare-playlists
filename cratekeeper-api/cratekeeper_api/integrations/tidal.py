"""Tidal adapter — Protocol + live (tidalapi via CLI) + mock."""

from __future__ import annotations

from typing import Protocol


class TidalAdapter(Protocol):
    def search_url(self, artist: str, title: str) -> str: ...
    def url_by_isrc(self, isrc: str) -> str | None: ...


class LiveTidalAdapter:
    """Real adapter — reuses cratekeeper.tidal_client (tidalapi + tidal-session.json)."""

    def __init__(self) -> None:
        self._session = None

    def _sess(self):
        if self._session is None:
            from cratekeeper.tidal_client import get_tidal_session
            self._session = get_tidal_session()
        return self._session

    def search_url(self, artist: str, title: str) -> str:
        from urllib.parse import quote
        return f"https://tidal.com/search?q={quote(f'{artist} {title}')}"

    def url_by_isrc(self, isrc: str) -> str | None:
        from cratekeeper.tidal_client import search_track_by_isrc
        return search_track_by_isrc(self._sess(), isrc)


class MockTidalAdapter:
    def __init__(self, isrc_map: dict[str, str | None] | None = None) -> None:
        self._isrc_map = isrc_map or {}

    def search_url(self, artist: str, title: str) -> str:
        from urllib.parse import quote
        return f"https://tidal.com/search?q={quote(f'{artist} {title}')}"

    def url_by_isrc(self, isrc: str) -> str | None:
        return self._isrc_map.get(isrc)


def get_tidal_adapter(use_mock: bool = False) -> TidalAdapter:
    return MockTidalAdapter() if use_mock else LiveTidalAdapter()
