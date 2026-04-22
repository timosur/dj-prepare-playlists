# DJ Prepare Playlists

A collection of **MCP servers and skills** for AI-assisted DJ set preparation. Designed to be used with coding agents like GitHub Copilot or Claude Code.

## Vision

As DJs working events like weddings, we receive large Spotify playlists full of guest wishes — unstructured and in random order. This project provides the AI tooling to turn that chaos into well-organized, playable sets.

### Core Workflows

#### 1. Event-Specific Playlist Sorting

For each event (e.g., a wedding), we take the raw wish playlist from Spotify and split it into **genre-based sub-playlists** — so during the gig we can simply switch between genre playlists instead of scrolling through hundreds of random tracks.

#### 2. Cross-Event Master Playlists

Across all events, we build and maintain **central genre playlists** that aggregate tracks from every wish list we've ever received. These master playlists grow over time and serve as our go-to library, organized by genre/era:

- **90s**, **2000s**, **80s**
- **Party Hits**, **Oldschool**, **Schlager**
- **Dance**, **Trance**, **Techno**, **House**
- **Pop**, **Rock**, **Hip-Hop/R&B**
- *(and more as needed)*

#### 3. Multi-Platform Sync

- **Spotify** is used for receiving wish playlists and for research/discovery.
- **Tidal** is our primary platform for live DJing.
- Final playlists should be available in **both Spotify and Tidal** — either as copies in both systems or synced between them.

### How It Works

This is **not** a standalone CLI app. It's a set of MCP (Model Context Protocol) servers that expose Spotify and Tidal APIs as tools to AI agents. The actual playlist sorting, genre classification, and organization logic is driven by the AI agent in conversation — using these tools to read playlists, analyze tracks, and create/populate new playlists.

## Project Structure

```
dj-playlist-prepare/
├── spotify-mcp/          # Spotify MCP server (TypeScript/Node.js)
│   ├── src/
│   ├── package.json
│   ├── tsconfig.json
│   └── spotify-config.example.json
├── tidal-mcp/            # Tidal MCP server (Python)
│   ├── tidal_mcp/
│   │   ├── server.py
│   │   ├── session.py
│   │   ├── auth.py
│   │   └── tools/
│   │       ├── search.py
│   │       ├── playlists.py
│   │       ├── albums.py
│   │       └── playback.py
│   └── pyproject.toml
└── README.md
```

## Current State

### Spotify MCP Server (`spotify-mcp/`)

A TypeScript MCP server exposing **29 tools** for full Spotify control:

| Category | Tools |
|---|---|
| **Search & Discovery** | Search tracks/albums/artists/playlists |
| **Playlist Management** | Create, update, add/remove/reorder tracks, list playlists |
| **Track Analysis** | Audio features (BPM, key, energy, danceability), artist genres |
| **Playback Control** | Play, pause, skip, queue, volume, devices |
| **Library** | Saved tracks, saved albums, recently played |

### Tidal MCP Server (`tidal-mcp/`)

A Python MCP server using [python-tidal](https://github.com/EbbLabs/python-tidal) exposing **19 tools**:

| Category | Tools |
|---|---|
| **Search & Discovery** | Search tracks/albums/artists/playlists, track details, artist details |
| **Playlist Management** | Create, update, get, list, add/remove tracks, add by ISRC, merge playlists |
| **Albums** | Get album details, album tracks, save/remove albums |
| **Favorites** | Get/add/remove favorite tracks, artists, albums |

## Setup

### Spotify MCP Server

#### Prerequisites

- Node.js
- A [Spotify Developer App](https://developer.spotify.com/dashboard) (Client ID & Secret)

#### Install & Configure

```bash
cd spotify-mcp
npm install
cp spotify-config.example.json spotify-config.json
# Edit spotify-config.json with your clientId and clientSecret
npm run auth    # Opens browser for Spotify OAuth login
npm run build
```

#### Scripts

| Script | Description |
|---|---|
| `npm run build` | Compile TypeScript |
| `npm run auth` | Run Spotify OAuth flow |
| `npm run lint` | Check code with Biome |
| `npm run lint:fix` | Auto-fix lint issues |
| `npm run typecheck` | Type-check without emitting |

### Tidal MCP Server

#### Prerequisites

- Python 3.11+
- A Tidal account (HiFi or HiFi Plus)

#### Install & Authenticate

```bash
cd tidal-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m tidal_mcp.auth   # Prints a link — open it to log in
```

### Connect to an MCP Client

Add both servers to your MCP client config (e.g., Claude Desktop, VS Code Copilot):

```json
{
  "mcpServers": {
    "spotify": {
      "command": "node",
      "args": ["/absolute/path/to/spotify-mcp/build/index.js"]
    },
    "tidal": {
      "command": "/absolute/path/to/tidal-mcp/.venv/bin/python",
      "args": ["-m", "tidal_mcp.server"]
    }
  }
}
```

## Design Decisions

### Tidal Integration

The Tidal MCP server is a **separate Python-based MCP server** using [python-tidal](https://github.com/EbbLabs/python-tidal). Since the Spotify server is TypeScript and python-tidal is Python, each platform gets its own MCP server — both registered in the client config side by side.

### Genre Classification

Genre sorting uses **Spotify artist genre tags combined with audio features** (BPM, energy, danceability) for more accurate classification. The key constraint: **keep the number of resulting playlists manageable**. It's better to have ~8–12 well-defined genre buckets than 30 micro-genres where you're searching again. The AI agent should consolidate similar genres into broader categories.

### Master Playlist Naming

Cross-event master playlists follow the pattern: **`[DJ] Genre`**

Examples: `[DJ] House`, `[DJ] 90s`, `[DJ] Schlager`, `[DJ] Party Hits`

### Duplicate Handling

When adding tracks to master playlists: **skip duplicates but report them** to the user so nothing is silently lost.

### Cross-Platform Track Matching

When syncing playlists from Spotify to Tidal: **skip tracks not found on Tidal and report them**. No fuzzy matching — only exact matches to avoid wrong versions.

### Playlist Metadata

Event-specific playlists include **event name and date** in their description (e.g., *"Wedding — Schmidt — 2026-06-15"*).

### Skills

Reusable agent workflows are packaged as **Copilot skills** (created via `/create-skill`), living in this repo for easy invocation from VS Code / GitHub Copilot.

## Roadmap

- [x] Spotify MCP Server (29 tools)
- [x] Tidal MCP Server (19 tools, Python, using python-tidal)
- [x] Copilot skills: `/sort-playlist-by-genre`, `/build-master-playlists`, `/sync-to-tidal`
- [ ] Cross-platform playlist sync (Spotify ↔ Tidal via ISRC matching)