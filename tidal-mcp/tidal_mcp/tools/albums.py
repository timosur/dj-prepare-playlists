"""Album tools for Tidal."""

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
        "duration_seconds": track.duration,
        "isrc": getattr(track, "isrc", None),
    }


def _format_album(album: tidalapi.Album) -> dict:
    return {
        "id": album.id,
        "name": album.name,
        "artist": album.artist.name if album.artist else "Unknown",
        "num_tracks": getattr(album, "num_tracks", None),
        "duration_seconds": getattr(album, "duration", None),
        "year": getattr(album, "year", None),
    }


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def get_album(album_id: str) -> str:
        """Get details for a Tidal album.

        Args:
            album_id: The Tidal album ID.
        """
        session = get_session()
        album = session.album(int(album_id))
        return json.dumps(_format_album(album), indent=2, default=str)

    @mcp.tool()
    def get_album_tracks(album_id: str, limit: int = 100) -> str:
        """Get tracks from a Tidal album.

        Args:
            album_id: The Tidal album ID.
            limit: Max tracks to return.
        """
        session = get_session()
        album = session.album(int(album_id))
        tracks = album.tracks(limit=limit)
        result = [_format_track(t) for t in tracks]
        return json.dumps(
            {"album": album.name, "tracks": result}, indent=2, default=str
        )

    @mcp.tool()
    def save_album(album_ids: list[str]) -> str:
        """Save albums to the user's favorites.

        Args:
            album_ids: List of Tidal album IDs to save.
        """
        session = get_session()
        for aid in album_ids:
            session.user.favorites.add_album(int(aid))
        return json.dumps({"saved": len(album_ids)}, indent=2)

    @mcp.tool()
    def remove_saved_album(album_ids: list[str]) -> str:
        """Remove albums from the user's favorites.

        Args:
            album_ids: List of Tidal album IDs to remove.
        """
        session = get_session()
        for aid in album_ids:
            session.user.favorites.remove_album(int(aid))
        return json.dumps({"removed": len(album_ids)}, indent=2)
