"""Tidal MCP Server — exposes Tidal API functionality as MCP tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from tidal_mcp.tools.albums import register as register_album_tools
from tidal_mcp.tools.playback import register as register_playback_tools
from tidal_mcp.tools.playlists import register as register_playlist_tools
from tidal_mcp.tools.search import register as register_search_tools

mcp = FastMCP("tidal-controller")

register_search_tools(mcp)
register_playlist_tools(mcp)
register_album_tools(mcp)
register_playback_tools(mcp)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
