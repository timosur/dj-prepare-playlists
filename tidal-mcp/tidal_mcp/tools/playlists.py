"""Playlist management tools for Tidal."""

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


def _format_playlist(playlist: tidalapi.Playlist) -> dict:
    return {
        "id": playlist.id,
        "name": playlist.name,
        "description": getattr(playlist, "description", None),
        "num_tracks": getattr(playlist, "num_tracks", None),
        "duration_seconds": getattr(playlist, "duration", None),
        "creator": playlist.creator.name if getattr(playlist, "creator", None) else None,
    }


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def get_my_playlists(limit: int = 50, offset: int = 0) -> str:
        """Get the current user's playlists.

        Args:
            limit: Max playlists to return.
            offset: Pagination offset.
        """
        session = get_session()
        playlists = session.user.playlist_and_favorite_playlists()
        result = [_format_playlist(p) for p in playlists[offset : offset + limit]]
        return json.dumps(result, indent=2, default=str)

    @mcp.tool()
    def get_playlist(playlist_id: str) -> str:
        """Get details for a specific playlist.

        Args:
            playlist_id: The Tidal playlist UUID.
        """
        session = get_session()
        playlist = session.playlist(playlist_id)
        return json.dumps(_format_playlist(playlist), indent=2, default=str)

    @mcp.tool()
    def get_playlist_tracks(
        playlist_id: str, limit: int = 100, offset: int = 0
    ) -> str:
        """Get tracks from a playlist.

        Args:
            playlist_id: The Tidal playlist UUID.
            limit: Max tracks to return.
            offset: Pagination offset.
        """
        session = get_session()
        playlist = session.playlist(playlist_id)
        tracks = playlist.tracks(limit=limit, offset=offset)
        result = [_format_track(t) for t in tracks]
        return json.dumps(
            {"playlist": playlist.name, "total": playlist.num_tracks, "tracks": result},
            indent=2,
            default=str,
        )

    @mcp.tool()
    def create_playlist(title: str, description: str = "") -> str:
        """Create a new playlist for the current user.

        Args:
            title: Playlist name.
            description: Optional playlist description.
        """
        session = get_session()
        playlist = session.user.create_playlist(title=title, description=description)
        return json.dumps(
            {"created": True, **_format_playlist(playlist)}, indent=2, default=str
        )

    @mcp.tool()
    def add_tracks_to_playlist(
        playlist_id: str,
        track_ids: list[str],
        allow_duplicates: bool = False,
    ) -> str:
        """Add tracks to an existing playlist.

        Args:
            playlist_id: The Tidal playlist UUID.
            track_ids: List of track IDs to add.
            allow_duplicates: Whether to allow duplicate tracks.
        """
        session = get_session()
        playlist = session.playlist(playlist_id)
        added = playlist.add(track_ids, allow_duplicates=allow_duplicates)
        return json.dumps(
            {
                "playlist": playlist.name,
                "requested": len(track_ids),
                "added": len(added) if added else len(track_ids),
            },
            indent=2,
            default=str,
        )

    @mcp.tool()
    def add_tracks_by_isrc(playlist_id: str, isrc_codes: list[str]) -> str:
        """Add tracks to a playlist by ISRC code (useful for cross-platform sync).

        Args:
            playlist_id: The Tidal playlist UUID.
            isrc_codes: List of ISRC codes to add.
        """
        session = get_session()
        playlist = session.playlist(playlist_id)
        results = []
        for isrc in isrc_codes:
            try:
                playlist.add_by_isrc(isrc)
                results.append({"isrc": isrc, "status": "added"})
            except Exception as e:
                results.append({"isrc": isrc, "status": "failed", "error": str(e)})
        return json.dumps(
            {"playlist": playlist.name, "results": results}, indent=2, default=str
        )

    @mcp.tool()
    def remove_tracks_from_playlist(playlist_id: str, track_ids: list[str]) -> str:
        """Remove tracks from a playlist.

        Args:
            playlist_id: The Tidal playlist UUID.
            track_ids: List of track IDs to remove.
        """
        session = get_session()
        playlist = session.playlist(playlist_id)
        # tidalapi expects integer indices or track IDs depending on version
        for tid in track_ids:
            try:
                playlist.remove_by_id(int(tid))
            except Exception:
                # Fallback: some versions use different method
                try:
                    playlist._remove(int(tid))
                except Exception:
                    pass
        return json.dumps(
            {"playlist": playlist.name, "removed": len(track_ids)},
            indent=2,
            default=str,
        )

    @mcp.tool()
    def update_playlist(
        playlist_id: str,
        title: str | None = None,
        description: str | None = None,
    ) -> str:
        """Update a playlist's name and/or description.

        Args:
            playlist_id: The Tidal playlist UUID.
            title: New playlist title (or None to keep current).
            description: New playlist description (or None to keep current).
        """
        session = get_session()
        playlist = session.playlist(playlist_id)
        if title is not None:
            playlist.edit(title=title)
        if description is not None:
            playlist.edit(description=description)
        # Reload
        playlist = session.playlist(playlist_id)
        return json.dumps(
            {"updated": True, **_format_playlist(playlist)}, indent=2, default=str
        )

    @mcp.tool()
    def merge_playlists(
        target_playlist_id: str,
        source_playlist_id: str,
        allow_duplicates: bool = False,
    ) -> str:
        """Merge all tracks from a source playlist into a target playlist.

        Args:
            target_playlist_id: The playlist UUID to add tracks to.
            source_playlist_id: The playlist UUID to copy tracks from.
            allow_duplicates: Whether to allow duplicate tracks.
        """
        session = get_session()
        target = session.playlist(target_playlist_id)
        target.merge(source_playlist_id, allow_duplicates=allow_duplicates)
        # Reload to get updated track count
        target = session.playlist(target_playlist_id)
        return json.dumps(
            {
                "merged": True,
                "target": target.name,
                "total_tracks": target.num_tracks,
            },
            indent=2,
            default=str,
        )
