"""DI container — picks live or mock adapters based on settings.test_mode.

The Anthropic client is **resolved lazily** by `anthropic_client_factory()`
because its API key lives in the encrypted settings table and may change at
runtime via PUT /settings/anthropic.
"""

from __future__ import annotations

from cratekeeper_api.config import get_settings
from cratekeeper_api.integrations.anthropic_client import (
    AnthropicTagClient,
    MockAnthropicTagClient,
    get_anthropic_tag_client,
)
from cratekeeper_api.integrations.musicbrainz import (
    MusicBrainzAdapter,
    get_musicbrainz_adapter,
)
from cratekeeper_api.integrations.spotify import SpotifyAdapter, get_spotify_adapter
from cratekeeper_api.integrations.tidal import TidalAdapter, get_tidal_adapter


class Container:
    spotify: SpotifyAdapter
    tidal: TidalAdapter
    musicbrainz: MusicBrainzAdapter
    # Override-only — handlers should call `anthropic_client_for(db)` instead so
    # the API key can be re-read after a settings PUT.
    anthropic: AnthropicTagClient | None

    def __init__(self) -> None:
        use_mock = get_settings().test_mode
        self.spotify = get_spotify_adapter(use_mock=use_mock)
        self.tidal = get_tidal_adapter(use_mock=use_mock)
        self.musicbrainz = get_musicbrainz_adapter(use_mock=use_mock)
        # In test mode, default to the mock so handlers don't need an API key.
        # In live mode, leave None and resolve per-call (see anthropic_client_for).
        self.anthropic = MockAnthropicTagClient() if use_mock else None


_container: Container | None = None


def get_container() -> Container:
    global _container
    if _container is None:
        _container = Container()
    return _container


def reset_container() -> None:
    """Force re-creation on next access (used by tests after env mutation)."""
    global _container
    _container = None


def set_spotify(adapter: SpotifyAdapter) -> None:
    get_container().spotify = adapter


def set_tidal(adapter: TidalAdapter) -> None:
    get_container().tidal = adapter


def set_anthropic(client: AnthropicTagClient) -> None:
    get_container().anthropic = client


def set_musicbrainz(adapter: MusicBrainzAdapter) -> None:
    get_container().musicbrainz = adapter


def anthropic_client_for(db) -> AnthropicTagClient:
    """Resolve the Anthropic client for a job.

    - If the container has an override (tests, or test_mode default mock), use it.
    - Otherwise, build a live client using the encrypted API key from settings.
    """
    c = get_container()
    if c.anthropic is not None:
        return c.anthropic
    from cratekeeper_api.secrets_store import get_setting

    api_key = get_setting(db, "anthropic_api_key")
    return get_anthropic_tag_client(use_mock=False, api_key=api_key)
