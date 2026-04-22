# DJ Playlist Prepare

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

This is **not** a standalone CLI app. It's a set of MCP (Model Context Protocol) servers that expose Spotify (and eventually Tidal) APIs as tools to AI agents. The actual playlist sorting, genre classification, and organization logic is driven by the AI agent in conversation — using these tools to read playlists, analyze tracks, and create/populate new playlists.

## Current State

### Spotify MCP Server (implemented)

An MCP server exposing **29 tools** for full Spotify control:

| Category | Tools |
|---|---|
| **Search & Discovery** | Search tracks/albums/artists/playlists |
| **Playlist Management** | Create, update, add/remove/reorder tracks, list playlists |
| **Track Analysis** | Audio features (BPM, key, energy, danceability), artist genres |
| **Playback Control** | Play, pause, skip, queue, volume, devices |
| **Library** | Saved tracks, saved albums, recently played |

### Tidal MCP Server (not yet implemented)

Planned: a separate **Python MCP server** using [python-tidal](https://github.com/EbbLabs/python-tidal) for creating and managing playlists on the DJ platform.

## Setup

### Prerequisites

- Node.js
- A [Spotify Developer App](https://developer.spotify.com/dashboard) (Client ID & Secret)

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Spotify

```bash
cp spotify-config.example.json spotify-config.json
```

Edit `spotify-config.json` and fill in your `clientId` and `clientSecret`.

### 3. Authenticate

```bash
npm run auth
```

This opens a browser for Spotify OAuth login. Tokens are saved to `spotify-config.json` and auto-refresh.

### 4. Build

```bash
npm run build
```

### 5. Connect to an MCP Client

Add to your MCP client config (e.g., Claude Desktop, VS Code Copilot):

```json
{
  "mcpServers": {
    "spotify": {
      "command": "node",
      "args": ["/absolute/path/to/build/index.js"]
    }
  }
}
```

## Scripts

| Script | Description |
|---|---|
| `npm run build` | Compile TypeScript |
| `npm run auth` | Run Spotify OAuth flow |
| `npm run lint` | Check code with Biome |
| `npm run lint:fix` | Auto-fix lint issues |
| `npm run typecheck` | Type-check without emitting |

## Design Decisions

### Tidal Integration

The Tidal MCP server will be a **separate Python-based MCP server** using [python-tidal](https://github.com/EbbLabs/python-tidal). Since the Spotify server is TypeScript and python-tidal is Python, each platform gets its own MCP server — both registered in the client config side by side.

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
- [ ] Tidal MCP Server (Python, using python-tidal)
- [ ] Copilot skills for common workflows (sort by genre, sync to Tidal, build master playlists)
- [ ] Cross-platform playlist sync (Spotify → Tidal)