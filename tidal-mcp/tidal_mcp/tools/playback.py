"""Playback and favorites tools for Tidal."""

from __future__ import annotations

import json

import tidalapi

from mcp.server.fastmcp import FastMCP

from tidal_mcp.session import get_session


def _format_track(track: tidalapi.Track) -> dict:
    return {
        "id": track.id,
        "name": track.name,
        "artist": track.artist.name if track.artist else "Unknown",
        "album": track.album.name if track.album else "Unknown",
        "duration_seconds": track.duration,
        "isrc": getattr(track, "isrc", None),
    }


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def get_favorite_tracks(limit: int = 50, offset: int = 0) -> str:
        """Get the user's favorite (saved) tracks.

        Args:
            limit: Max tracks to return.
            offset: Pagination offset.
        """
        session = get_session()
        tracks = session.user.favorites.tracks(limit=limit, offset=offset)
        result = [_format_track(t) for t in tracks]
        return json.dumps(result, indent=2, default=str)

    @mcp.tool()
    def add_favorite_tracks(track_ids: list[str]) -> str:
        """Add tracks to the user's favorites.

        Args:
            track_ids: List of Tidal track IDs to favorite.
        """
        session = get_session()
        session.user.favorites.add_track(track_ids)
        return json.dumps({"favorited": len(track_ids)}, indent=2)

    @mcp.tool()
    def remove_favorite_tracks(track_ids: list[str]) -> str:
        """Remove tracks from the user's favorites.

        Args:
            track_ids: List of Tidal track IDs to un-favorite.
        """
        session = get_session()
        for tid in track_ids:
            session.user.favorites.remove_track(int(tid))
        return json.dumps({"removed": len(track_ids)}, indent=2)

    @mcp.tool()
    def get_favorite_artists(limit: int = 50, offset: int = 0) -> str:
        """Get the user's favorite artists.

        Args:
            limit: Max artists to return.
            offset: Pagination offset.
        """
        session = get_session()
        artists = session.user.favorites.artists(limit=limit, offset=offset)
        result = [{"id": a.id, "name": a.name} for a in artists]
        return json.dumps(result, indent=2, default=str)

    @mcp.tool()
    def get_favorite_albums(limit: int = 50, offset: int = 0) -> str:
        """Get the user's favorite albums.

        Args:
            limit: Max albums to return.
            offset: Pagination offset.
        """
        session = get_session()
        albums = session.user.favorites.albums(limit=limit, offset=offset)
        result = [
            {
                "id": a.id,
                "name": a.name,
                "artist": a.artist.name if a.artist else "Unknown",
            }
            for a in albums
        ]
        return json.dumps(result, indent=2, default=str)
