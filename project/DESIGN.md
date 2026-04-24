# Cratekeeper Design System

Cratekeeper is a local-first web app for DJs: it turns a Spotify wish-playlist into a classified, mood-analyzed, properly-tagged event folder — ready to load into a DJ set. The stack is FastAPI + React + Vite + TypeScript; the UI runs only on localhost for a single operator.

The visual language is deliberately Spotify-adjacent: DJs already live inside Spotify, and a familiar dark aesthetic keeps the tool feeling native to the music world. The UI is a tool, not a player — density and workflow clarity matter more than animation.

## 1. Visual Theme & Atmosphere

The design philosophy is **"pipeline-first darkness"** — every surface is a shade of charcoal (`#121212`, `#181818`, `#1f1f1f`) so that status colors, confidence scores, waveform energy levels, and track metadata can glow against it. Color is reserved for state: active jobs, warnings, errors, and success confirmations.

**Key Characteristics:**
- Near-black immersive dark theme (`#121212`–`#1f1f1f`) — UI disappears behind content
- Cratekeeper Green (`#1ed760`, same hue as Spotify) as the singular brand accent — used only for active states, primary CTAs, and confirmed success
- Inter (system-fallback-friendly) as the primary typeface — no proprietary font dependency since this is a local tool
- Pill buttons (500px–9999px) and circular icon controls (50%) — rounded, consistent with music-app conventions
- Uppercase button labels with wide letter-spacing (1.4px–2px) for action labels
- Heavy shadows on elevated elements (`rgba(0,0,0,0.5) 0px 8px 24px`)
- Semantic colors: negative red (`#f3727f`) for errors/missing, warning orange (`#ffa42b`) for advisories, blue (`#539df5`) for informational states
- Track metadata and match confidence are the primary color sources — the chrome is achromatic by design

## 2. Color Palette & Roles

### Primary Brand
- **Cratekeeper Green** (`#1ed760`): Primary brand accent — active step indicator, primary CTAs, confirmed success
- **Near Black** (`#121212`): Deepest background surface
- **Dark Surface** (`#181818`): Cards, containers, elevated surfaces
- **Mid Dark** (`#1f1f1f`): Button backgrounds, interactive surfaces

### Text
- **White** (`#ffffff`): `--text-base`, primary text
- **Silver** (`#b3b3b3`): Secondary text, muted labels, inactive nav
- **Near White** (`#cbcbcb`): Slightly brighter secondary text
- **Light** (`#fdfdfd`): Near-pure white for maximum emphasis

### Semantic
- **Negative Red** (`#f3727f`): Errors, missing tracks, failed jobs, quality-check failures
- **Warning Orange** (`#ffa42b`): Advisory quality-check warnings, stale-build banners, symlink mode
- **Info Blue** (`#539df5`): Informational states, ETA hints, log viewer highlights

### Surface & Border
- **Dark Card** (`#252525`): Elevated card surface
- **Mid Card** (`#272727`): Alternate card surface
- **Border Gray** (`#4d4d4d`): Button borders on dark
- **Light Border** (`#7c7c7c`): Outlined button borders, muted links
- **Separator** (`#b3b3b3`): Divider lines
- **Light Surface** (`#eeeeee`): Light-mode buttons (rare)
- **Spotify Green Border** (`#1db954`): Green accent border variant

### Shadows
- **Heavy** (`rgba(0,0,0,0.5) 0px 8px 24px`): Dialogs, menus, elevated panels
- **Medium** (`rgba(0,0,0,0.3) 0px 8px 8px`): Cards, dropdowns
- **Inset Border** (`rgb(18,18,18) 0px 1px 0px, rgb(124,124,124) 0px 0px 0px 1px inset`): Input border-shadow combo

## 3. Typography Rules

### Font Family
- **UI / Body**: `Inter`, fallback: `system-ui, -apple-system, Helvetica Neue, Arial, sans-serif`
- No proprietary fonts — this is a local tool, not a public product

### Hierarchy

| Role | Font | Size | Weight | Line Height | Letter Spacing | Notes |
|------|------|------|--------|-------------|----------------|-------|
| Page Title | Inter | 24px (1.50rem) | 700 | normal | normal | Event name, section headers |
| Section Heading | Inter | 18px (1.13rem) | 600 | 1.30 (tight) | normal | Step names, panel headers |
| Body Bold | Inter | 16px (1.00rem) | 700 | normal | normal | Emphasized track/field |
| Body | Inter | 16px (1.00rem) | 400 | normal | normal | Standard body |
| Button Uppercase | Inter | 14px (0.88rem) | 600–700 | 1.00 (tight) | 1.4px–2px | `text-transform: uppercase`, pipeline action buttons |
| Button | Inter | 14px (0.88rem) | 700 | normal | 0.14px | Standard button |
| Nav Link Bold | Inter | 14px (0.88rem) | 700 | normal | normal | Active navigation |
| Nav Link | Inter | 14px (0.88rem) | 400 | normal | normal | Inactive nav |
| Caption Bold | Inter | 14px (0.88rem) | 700 | 1.50–1.54 | normal | Confidence scores, match status |
| Caption | Inter | 14px (0.88rem) | 400 | normal | normal | Track metadata, timestamps |
| Small Bold | Inter | 12px (0.75rem) | 700 | 1.50 | normal | Genre bucket tags, counts |
| Small | Inter | 12px (0.75rem) | 400 | normal | normal | Log lines, file paths |
| Badge | Inter | 10.5px (0.66rem) | 600 | 1.33 | normal | Status badges, step indicators |
| Micro | Inter | 10px (0.63rem) | 400 | normal | normal | Smallest metadata |

### Principles
- **Bold/regular binary**: Most text is either 700 (bold) or 400 (regular), with 600 used sparingly for section headings.
- **Uppercase action buttons**: Pipeline step action buttons (Enrich, Classify, Tag, Build…) use uppercase + wide letter-spacing (1.4px–2px) to distinguish system commands from content labels.
- **Compact sizing**: The range is 10px–24px. Track lists, log viewers, and review tables must pack information efficiently — this is a tool, not a marketing page.
- **Numeric data uses tabular figures**: match confidence percentages, token counts, and BPM values should use `font-variant-numeric: tabular-nums` so columns align.

## 4. Component Stylings

### Buttons

**Primary Action (Pipeline Step)**
- Background: `#1ed760` (green)
- Text: `#000000`
- Padding: 8px 24px
- Radius: 9999px (full pill)
- Label: uppercase, 1.4px letter-spacing
- Use: Enrich, Classify, Scan, Analyze, Tag, Build, Sync — one primary action per step

**Secondary / Outline**
- Background: transparent
- Text: `#ffffff`
- Border: `1px solid #7c7c7c`
- Padding: 4px 16px
- Radius: 9999px
- Use: Skip, Cancel, "Full rescan", "Override and proceed"

**Destructive Confirm**
- Background: `#f3727f` (red) after a confirmation prompt
- Text: `#ffffff`
- Radius: 9999px
- Use: Write tags, delete event — shown only after an explicit confirm step

**Dark Pill (Navigation / Filter)**
- Background: `#1f1f1f`
- Text: `#ffffff` (active) / `#b3b3b3` (inactive)
- Radius: 9999px
- Use: Step navigation, confidence-filter pills in the Review step

**Circular Icon Control**
- Radius: 50%
- Padding: 12px
- Use: Sidebar icon navigation, per-track action icons

### Cards & Containers
- Background: `#181818` or `#1f1f1f`
- Radius: 6px–8px
- No visible borders on most cards
- Hover: slight background lightening (`#282828`)
- Shadow: `rgba(0,0,0,0.3) 0px 8px 8px` on elevated panels

### Inputs & Search
- Background: `#1f1f1f`
- Text: `#ffffff`
- Radius: 500px (pill)
- Padding: 12px 48px (icon-aware)
- Focus: `1px solid #ffffff` outline
- Use: Playlist URL intake, track search, filter inputs

### Progress Bar (Job Runner)
- Track: `#282828`
- Fill: `#1ed760` (active) → `#b3b3b3` (complete)
- Height: 4px, no radius rounding on fill
- Accompanies every long-running job step (Enrich, Scan, Analyze, Classify, Match)

### Status Badge
- Pill shape, 10.5px/600
- Colors: green (`#1ed760`) = matched/done, orange (`#ffa42b`) = warning/partial, red (`#f3727f`) = missing/failed, gray (`#b3b3b3`) = pending
- Use: Per-track match status, per-step pipeline state

### Log Viewer
- Background: `#121212` (deepest level)
- Text: `#b3b3b3` (default), `#ffa42b` (warnings), `#f3727f` (errors), `#1ed760` (success lines)
- Font: 12px/400 monospace fallback
- Renders SSE log channel output alongside each job's progress bar

### Navigation
- Dark sidebar with Inter 14px weight 700 for active, 400 for inactive
- `#b3b3b3` muted color for inactive items, `#ffffff` for active
- Sections: **Dashboard**, **Events** (one entry per active event), **Library**, **Settings**
- Circular icon buttons (50% radius)

## 5. Layout Principles

### Spacing System
- Base unit: 8px
- Scale: 1px, 2px, 3px, 4px, 5px, 6px, 8px, 10px, 12px, 14px, 15px, 16px, 20px

### App Shell
- **Sidebar (fixed, ~240px)**: app logo, Dashboard, event list, Library, Settings; collapses to icon-only on narrow viewports
- **Main content area**: fills remaining width; contains either the Dashboard or a single-event workflow view
- **No bottom now-playing bar** — this is a pipeline tool, not a player

### Event Workflow Layout
The guided event workflow uses a **step-rail + detail pane** model:
- Left rail: numbered step list (Intake → Enrich → Classify → Review → Scan/Match → Analyze → Tagging → Build → Sync), each with a status badge
- Right/main pane: the active step's full UI — progress bar, log viewer, data tables, or action panels
- **No auto-advance**: each step requires explicit user confirmation before the pipeline moves forward

### Dashboard Layout
- Card grid: one card per active event showing name, slug, current step, match rate, last-run timestamp
- Empty state with a prominent "New Event" CTA (green pill button)
- Multi-event: users can switch between events freely; each event preserves its own step state

### Review / Track-List Tables
- Full-width table with sticky header
- Columns: track name, artist, bucket, confidence %, match status, LLM tags, actions
- Default sort: low-confidence first (mirrors `crate review` behavior)
- Bulk-select via checkboxes; bulk actions toolbar appears when rows are selected

### Whitespace Philosophy
- **Dense but scannable**: 100-track playlist tables must be readable without scrolling past a screenful per track. Compact row heights (40px–48px) with 8px cell padding.
- **Dark compression**: the dark background provides visual separation between dense rows without needing large row gaps.

### Border Radius Scale
- Minimal (2px): Badges, explicit-content tags
- Subtle (4px): Small inputs, table cells
- Standard (6px): Cards, panels
- Comfortable (8px): Dialogs, modals
- Large (100px): Large pill buttons
- Pill (500px): Search input, primary nav buttons
- Full Pill (9999px): Step action buttons, filter pills
- Circle (50%): Icon buttons, avatars

## 6. Depth & Elevation

| Level | Treatment | Use |
|-------|-----------|-----|
| Base (Level 0) | `#121212` background | Deepest layer, page background |
| Surface (Level 1) | `#181818` or `#1f1f1f` | Cards, sidebar, containers |
| Elevated (Level 2) | `rgba(0,0,0,0.3) 0px 8px 8px` | Dropdown menus, hover cards |
| Dialog (Level 3) | `rgba(0,0,0,0.5) 0px 8px 24px` | Modals, overlays, menus |
| Inset (Border) | `rgb(18,18,18) 0px 1px 0px, rgb(124,124,124) 0px 0px 0px 1px inset` | Input borders |

**Shadow Philosophy**: Cratekeeper uses heavy shadows on dark backgrounds. The 0.5 opacity shadow at 24px blur creates a "floating in darkness" effect for modals and quality-check panels, while the 0.3 opacity at 8px blur provides a subtle card lift. The inset border-shadow combo on inputs creates a recessed, tactile quality without adding a visible border color to the palette.

## 7. Do's and Don'ts

### Do
- Use near-black backgrounds (`#121212`–`#1f1f1f`) — depth through shade variation, not borders
- Apply Cratekeeper Green (`#1ed760`) only for active states, primary pipeline action buttons, and success confirmations
- Use pill shape (500px–9999px) for all action buttons — circular (50%) for icon controls
- Apply uppercase + wide letter-spacing (1.4px–2px) on pipeline step action labels
- Show a live ETA alongside progress bars for rate-limited steps (MusicBrainz enrich: 1 req/sec × pending)
- Show token/cost estimate before dispatching LLM classifier jobs (user must confirm before spending)
- Surface structured errors with a recovery action — never a blank spinner or empty-result success
- Require explicit user confirmation for all destructive ops (tag writes, event folder build, sync)
- Keep typography compact (10px–24px range) — tables must pack 100 tracks without overwhelming

### Don't
- Don't use Cratekeeper Green decoratively or on backgrounds — it signals "active / success / proceed only"
- Don't auto-advance between pipeline steps — each step needs an explicit "Continue" click
- Don't use light backgrounds for primary surfaces — dark immersion is core to the music-tool feel
- Don't skip the pill/circle geometry on buttons — square buttons break the visual identity
- Don't use thin/subtle shadows — on dark backgrounds, shadows need `0.3–0.5` opacity to be visible
- Don't add extra brand colors beyond green + achromatic grays + the three semantic colors
- Don't expose raw file-system paths as plain text where a structured picker or link would be safer
- Don't fail silently — if `/Volumes/Music` is unmounted, show a banner with a re-check action, not an empty result

## 8. Responsive Behavior

Cratekeeper runs on localhost for a single operator on a desktop Mac. Responsive design is a secondary concern — the primary viewport is a ~1280px+ desktop browser. Sidebar collapses to icons at narrower viewports; the step-rail collapses to a top stepper on viewports below 896px.

| Name | Width | Key Changes |
|------|-------|-------------|
| Desktop | >1024px | Full sidebar + step rail + detail pane |
| Desktop Small | 896–1024px | Sidebar collapsed to icons |
| Tablet | 576–896px | Step rail becomes top stepper; single-column content |
| Mobile | <576px | Not a primary target; best-effort single-column |

### Collapsing Strategy
- Sidebar: full labels → icon-only → hidden off-canvas
- Step rail: vertical sidebar → horizontal top stepper
- Track tables: all columns → hide LLM tags column → hide confidence column

## 9. Domain-Specific Patterns

### Pipeline Step States
Every step in the event workflow has one of five states, rendered with a badge + icon in the step rail:
- **Pending** (gray `#4d4d4d`): not yet started
- **Running** (green `#1ed760`, animated pulse): job in progress
- **Needs Review** (orange `#ffa42b`): step completed but user action required before continuing
- **Complete** (green `#1ed760`, static): step finished, user confirmed
- **Failed** (red `#f3727f`): job errored; log viewer expanded automatically

### Quality Checks Pre-Flight Panel
- Modal (Level 3 elevation: `rgba(0,0,0,0.5) 0px 8px 24px`)
- Checklist rows: icon (green tick / orange warning / red X) + label + optional detail text
- Warnings are advisory — show an "Acknowledge and proceed" secondary action
- Failures block: primary button disabled; only "Override and proceed" (red outline) is available, which requires typing a confirmation phrase
- Override action is written to the audit log automatically

### Missing-Track Recovery Row
- Highlighted with a red-tinted row background (`rgba(243,114,127,0.08)`)
- Per-track actions: "Open in Tidal" (external link icon), "Rescan this track" (circular icon), "Mark as acquire-later" (bookmark icon)
- "Mark as acquire-later" adds the track to `_missing.txt` at build time and dims the row

### Stale-Build Banner
- Full-width warning stripe (`#ffa42b` left border, `#1f1f1f` background) above the Build step
- Message: "Tags changed since last build — rebuild to propagate"
- One-click "Rebuild now" action (green pill) on the right side of the banner

### LLM Token / Cost Estimate
- Shown as an inline info card before the Tagging job dispatches
- Format: "~12k input tokens · ~2k output tokens · est. $0.04"
- During the run, live token usage and cache-hit ratio stream from the SSE log channel
- Post-run: cumulative totals persisted and visible in Settings → Anthropic section

### Energy Distribution & BPM Histogram
- Rendered after Analyze step completes as first-class UI, not log lines
- Energy distribution: three-bar horizontal bar chart (Low / Mid / High counts + percentages)
- BPM histogram: bucketed bar chart (e.g., 110–120, 120–130, 130–140, 140+)
- Both charts use `#1ed760` fill on `#282828` background bars; axis labels at 12px/400

### Genre Bucket Tag Pill
- Small pill badge (4px radius, 10.5px/600)
- Background: `#1f1f1f`, text: `#b3b3b3` for standard buckets
- High-confidence bucket: text `#ffffff`
- Low-confidence bucket (< 0.5): `#ffa42b` text + optional warning icon
- LLM genre suggestion (different from current bucket): blue (`#539df5`) text + "suggestion" label
6. Album art provides all the color — the UI stays achromatic
