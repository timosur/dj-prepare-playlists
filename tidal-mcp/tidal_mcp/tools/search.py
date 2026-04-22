"""Search & discovery tools for Tidal."""

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


def _format_album(album: tidalapi.Album) -> dict:
    return {
        "id": album.id,
        "name": album.name,
        "artist": album.artist.name if album.artist else "Unknown",
        "num_tracks": getattr(album, "num_tracks", None),
        "duration_seconds": getattr(album, "duration", None),
        "year": getattr(album, "year", None),
    }


def _format_artist(artist: tidalapi.Artist) -> dict:
    return {
        "id": artist.id,
        "name": artist.name,
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
    def search_tidal(
        query: str,
        search_type: str = "all",
        limit: int = 20,
    ) -> str:
        """Search Tidal for tracks, albums, artists, or playlists.

        Args:
            query: Search query string.
            search_type: One of 'all', 'track', 'album', 'artist', 'playlist'.
            limit: Max results per category (up to 300).
        """
        session = get_session()

        model_map = {
            "track": [tidalapi.Track],
            "album": [tidalapi.Album],
            "artist": [tidalapi.Artist],
            "playlist": [tidalapi.Playlist],
        }

        models = model_map.get(search_type)
        results = session.search(query, models=models, limit=limit)

        output: dict = {}
        if results.get("artists"):
            output["artists"] = [_format_artist(a) for a in results["artists"]]
        if results.get("albums"):
            output["albums"] = [_format_album(a) for a in results["albums"]]
        if results.get("tracks"):
            output["tracks"] = [_format_track(t) for t in results["tracks"]]
        if results.get("playlists"):
            output["playlists"] = [_format_playlist(p) for p in results["playlists"]]
        if results.get("top_hit"):
            top = results["top_hit"]
            output["top_hit"] = {"name": getattr(top, "name", str(top)), "type": type(top).__name__}

        return json.dumps(output, indent=2, default=str)

    @mcp.tool()
    def get_track_details(track_ids: list[str]) -> str:
        """Get detailed info for one or more Tidal tracks.

        Args:
            track_ids: List of Tidal track IDs (up to 50).
        """
        session = get_session()
        tracks = []
        for tid in track_ids[:50]:
            try:
                track = session.track(int(tid))
                tracks.append(_format_track(track))
            except Exception as e:
                tracks.append({"id": tid, "error": str(e)})
        return json.dumps(tracks, indent=2, default=str)

    @mcp.tool()
    def get_artist_details(artist_ids: list[str]) -> str:
        """Get detailed info for one or more Tidal artists.

        Args:
            artist_ids: List of Tidal artist IDs (up to 50).
        """
        session = get_session()
        artists = []
        for aid in artist_ids[:50]:
            try:
                artist = session.artist(int(aid))
                info = _format_artist(artist)
                # Try to get top tracks for genre inference
                try:
                    top_tracks = artist.get_top_tracks(limit=5)
                    info["top_tracks"] = [_format_track(t) for t in top_tracks]
                except Exception:
                    pass
                artists.append(info)
            except Exception as e:
                artists.append({"id": aid, "error": str(e)})
        return json.dumps(artists, indent=2, default=str)
