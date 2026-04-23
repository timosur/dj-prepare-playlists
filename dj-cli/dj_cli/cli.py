"""DJ CLI — playlist preparation pipeline."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from dj_cli.models import EventPlan

app = typer.Typer(help="DJ playlist preparation CLI")
console = Console()

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


@app.command()
def fetch(
    playlist_url: str = typer.Argument(help="Spotify playlist URL or ID"),
    output: Path = typer.Option(None, "--output", "-o", help="Output JSON path (default: data/<playlist-name>.json)"),
) -> None:
    """Fetch all tracks from a Spotify playlist, enrich with artist genres, save to JSON."""
    from dj_cli.spotify_client import (
        extract_playlist_id,
        fetch_artist_genres,
        fetch_playlist_tracks,
        get_spotify_client,
    )

    console.print("[bold]Connecting to Spotify...[/bold]")
    sp = get_spotify_client()

    playlist_id = extract_playlist_id(playlist_url)
    console.print(f"Fetching playlist [cyan]{playlist_id}[/cyan]...")

    playlist_name, tracks = fetch_playlist_tracks(sp, playlist_id)
    console.print(f"Found [green]{len(tracks)}[/green] tracks in '{playlist_name}'")

    # Collect unique artist IDs
    all_artist_ids = list({aid for t in tracks for aid in t.artist_ids})
    console.print(f"Fetching genres for [cyan]{len(all_artist_ids)}[/cyan] unique artists...")
    artist_genres = fetch_artist_genres(sp, all_artist_ids)

    # Enrich tracks with genres
    for track in tracks:
        genres: list[str] = []
        for aid in track.artist_ids:
            genres.extend(artist_genres.get(aid, []))
        track.artist_genres = list(set(genres))

    # Save
    plan = EventPlan(
        source_playlist_id=playlist_id,
        source_playlist_name=playlist_name,
        tracks=tracks,
    )

    if output is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = playlist_name.lower().replace(" ", "-").replace("/", "-")[:50]
        output = DATA_DIR / f"{safe_name}.json"

    plan.save(output)
    console.print(f"Saved to [green]{output}[/green]")


@app.command()
def classify(
    input_file: Path = typer.Argument(help="Path to fetched playlist JSON"),
    min_bucket_size: int = typer.Option(3, "--min-bucket", help="Minimum tracks per bucket (smaller buckets get merged)"),
    enrich: bool = typer.Option(False, "--enrich", "-e", help="Enrich missing genres via MusicBrainz before classifying"),
) -> None:
    """Classify tracks into genre buckets and print a summary."""
    from dj_cli.classifier import classify_tracks, consolidate_small_buckets

    plan = EventPlan.load(input_file)
    console.print(f"Loaded [green]{len(plan.tracks)}[/green] tracks from '{plan.source_playlist_name}'")

    if enrich:
        from dj_cli.musicbrainz_client import enrich_tracks_genres

        missing = sum(1 for t in plan.tracks if not t.artist_genres and t.isrc)
        if missing:
            console.print(f"Enriching [cyan]{missing}[/cyan] tracks via MusicBrainz (≈{missing}s)...")
            def _progress(i, total, track, genres):
                tag = f" → {', '.join(genres[:3])}" if genres else " → no tags"
                console.print(f"  [{i}/{total}] {track.display_name()}{tag}")
            enriched = enrich_tracks_genres(plan.tracks, progress_callback=_progress)
            console.print(f"Enriched [green]{enriched}[/green] of {missing} tracks with MusicBrainz tags")
        else:
            console.print("[dim]No tracks need enrichment[/dim]")

    classify_tracks(plan.tracks)
    consolidate_small_buckets(plan.tracks, min_size=min_bucket_size)

    # Print summary table
    buckets = plan.bucket_summary()
    table = Table(title=f"Genre Classification — {plan.source_playlist_name} ({len(plan.tracks)} tracks)")
    table.add_column("Bucket", style="cyan")
    table.add_column("Tracks", justify="right", style="green")
    table.add_column("High", justify="right")
    table.add_column("Medium", justify="right")
    table.add_column("Low", justify="right")

    for bucket_name, bucket_tracks in buckets.items():
        high = sum(1 for t in bucket_tracks if t.confidence == "high")
        med = sum(1 for t in bucket_tracks if t.confidence == "medium")
        low = sum(1 for t in bucket_tracks if t.confidence == "low")
        table.add_row(bucket_name, str(len(bucket_tracks)), str(high), str(med), str(low))

    console.print(table)

    # Save classified version
    output = input_file.with_suffix(".classified.json")
    plan.save(output)
    console.print(f"Saved classified plan to [green]{output}[/green]")


@app.command()
def enrich(
    input_file: Path = typer.Argument(help="Path to fetched/classified playlist JSON"),
) -> None:
    """Enrich tracks missing genre data via MusicBrainz ISRC lookup."""
    from dj_cli.musicbrainz_client import enrich_tracks_genres

    plan = EventPlan.load(input_file)
    missing_genres = sum(1 for t in plan.tracks if not t.artist_genres and t.isrc)
    missing_year = sum(1 for t in plan.tracks if not t.release_year and t.isrc)
    candidates = sum(1 for t in plan.tracks if (not t.artist_genres or not t.release_year) and t.isrc)
    console.print(f"Loaded [green]{len(plan.tracks)}[/green] tracks, [cyan]{missing_genres}[/cyan] missing genres, [cyan]{missing_year}[/cyan] missing release year")

    if not candidates:
        console.print("[green]All tracks already have genre and year data![/green]")
        return

    console.print(f"Querying MusicBrainz for {candidates} tracks (≈{candidates}s due to rate limit)...")

    def _progress(i, total, track, genres, mb_year):
        parts = []
        if genres:
            parts.append(", ".join(genres[:3]))
        if mb_year:
            parts.append(f"year={mb_year}")
        tag = f" → {'; '.join(parts)}" if parts else " → no tags"
        console.print(f"  [{i}/{total}] {track.display_name()}{tag}")

    enriched = enrich_tracks_genres(plan.tracks, progress_callback=_progress)
    console.print(f"\nEnriched [green]{enriched}[/green] of {candidates} tracks")

    plan.save(input_file)
    console.print(f"Saved to [green]{input_file}[/green]")


@app.command()
def review(
    input_file: Path = typer.Argument(help="Path to classified JSON"),
) -> None:
    """Print tracks with low-confidence classification for manual review."""
    plan = EventPlan.load(input_file)

    low_conf = [t for t in plan.tracks if t.confidence == "low"]
    med_conf = [t for t in plan.tracks if t.confidence == "medium"]

    if not low_conf and not med_conf:
        console.print("[green]All tracks classified with high confidence![/green]")
        return

    if med_conf:
        table = Table(title=f"Medium Confidence ({len(med_conf)} tracks)")
        table.add_column("#", justify="right", style="dim")
        table.add_column("Track")
        table.add_column("Bucket", style="cyan")
        table.add_column("Year", justify="right")
        table.add_column("Genres", style="dim")

        for i, t in enumerate(med_conf, 1):
            table.add_row(str(i), t.display_name(), t.bucket or "?", str(t.release_year or "?"), ", ".join(t.artist_genres[:3]) or "none")

        console.print(table)

    if low_conf:
        table = Table(title=f"Low Confidence / Fallback ({len(low_conf)} tracks)")
        table.add_column("#", justify="right", style="dim")
        table.add_column("Track")
        table.add_column("Bucket", style="yellow")
        table.add_column("Year", justify="right")
        table.add_column("Genres", style="dim")

        for i, t in enumerate(low_conf, 1):
            table.add_row(str(i), t.display_name(), t.bucket or "?", str(t.release_year or "?"), ", ".join(t.artist_genres[:3]) or "none")

        console.print(table)

    console.print(f"\nEdit the classified JSON directly to move tracks between buckets.")
    console.print(f"Or use the LLM skill for AI-assisted review.")


@app.command(name="create-playlists")
def create_playlists(
    input_file: Path = typer.Argument(help="Path to classified JSON"),
    event: str = typer.Option(..., "--event", "-e", help="Event name (e.g., 'Wedding Tim & Lea')"),
    date: str = typer.Option(..., "--date", "-d", help="Event date (e.g., '2026-04-22')"),
) -> None:
    """Create Spotify sub-playlists from classified tracks."""
    from dj_cli.spotify_client import (
        add_tracks_to_playlist,
        create_playlist,
        get_spotify_client,
    )

    plan = EventPlan.load(input_file)
    plan.event_name = event
    plan.event_date = date

    sp = get_spotify_client()
    buckets = plan.bucket_summary()

    console.print(f"Creating [cyan]{len(buckets)}[/cyan] playlists for '{event}'...")

    for bucket_name, bucket_tracks in buckets.items():
        if bucket_name == "Unclassified":
            continue

        playlist_name = f"{event} — {bucket_name}"
        description = f"{event} — {date} — {bucket_name} — Auto-sorted from wish playlist"

        playlist_id = create_playlist(sp, playlist_name, description)
        track_ids = [t.id for t in bucket_tracks]
        add_tracks_to_playlist(sp, playlist_id, track_ids)

        plan.created_playlists[bucket_name] = playlist_id
        console.print(f"  ✓ {playlist_name} — {len(track_ids)} tracks")

    plan.save(input_file)
    console.print(f"\n[green]Done![/green] Created {len(plan.created_playlists)} playlists.")


@app.command(name="build-masters")
def build_masters(
    input_file: Path = typer.Argument(help="Path to classified JSON"),
) -> None:
    """Add classified tracks to cross-event [DJ] master playlists on Spotify."""
    from dj_cli.spotify_client import (
        add_tracks_to_playlist,
        create_playlist,
        get_playlist_track_ids,
        get_spotify_client,
        get_user_playlists,
    )

    plan = EventPlan.load(input_file)
    sp = get_spotify_client()
    buckets = plan.bucket_summary()

    # Find existing [DJ] playlists
    user_playlists = get_user_playlists(sp)
    dj_playlists = {p["name"]: p["id"] for p in user_playlists if p["name"].startswith("[DJ] ")}

    console.print(f"Found [cyan]{len(dj_playlists)}[/cyan] existing [DJ] master playlists")

    total_added = 0
    total_dupes = 0

    for bucket_name, bucket_tracks in buckets.items():
        if bucket_name == "Unclassified":
            continue

        master_name = f"[DJ] {bucket_name}"
        track_ids = [t.id for t in bucket_tracks]

        if master_name in dj_playlists:
            playlist_id = dj_playlists[master_name]
            existing_ids = get_playlist_track_ids(sp, playlist_id)
            new_ids = [tid for tid in track_ids if tid not in existing_ids]
            dupes = len(track_ids) - len(new_ids)
        else:
            playlist_id = create_playlist(sp, master_name, f"Cross-event master playlist — {bucket_name}")
            dj_playlists[master_name] = playlist_id
            new_ids = track_ids
            dupes = 0

        if new_ids:
            add_tracks_to_playlist(sp, playlist_id, new_ids)

        total_added += len(new_ids)
        total_dupes += dupes

        status = f"+{len(new_ids)} new"
        if dupes:
            status += f", {dupes} dupes skipped"
        console.print(f"  {master_name} — {status}")

    console.print(f"\n[green]Done![/green] Added {total_added} tracks, skipped {total_dupes} duplicates.")


@app.command(name="sync-to-tidal")
def sync_to_tidal(
    input_file: Path = typer.Argument(help="Path to classified JSON"),
) -> None:
    """Sync classified playlists to Tidal via ISRC matching."""
    from dj_cli.tidal_client import (
        add_tracks_by_isrc,
        create_playlist,
        get_tidal_session,
    )

    plan = EventPlan.load(input_file)
    session = get_tidal_session()
    buckets = plan.bucket_summary()

    event_prefix = plan.event_name or plan.source_playlist_name

    console.print(f"Syncing [cyan]{len(buckets)}[/cyan] playlists to Tidal...")

    total_added = 0
    total_failed = 0

    for bucket_name, bucket_tracks in buckets.items():
        if bucket_name == "Unclassified":
            continue

        isrcs = [t.isrc for t in bucket_tracks if t.isrc]
        if not isrcs:
            console.print(f"  ✗ {bucket_name} — no ISRCs available, skipping")
            continue

        playlist_name = f"{event_prefix} — {bucket_name}"
        tidal_playlist_id = create_playlist(session, playlist_name)
        added, failed = add_tracks_by_isrc(session, tidal_playlist_id, isrcs)

        plan.tidal_playlists[bucket_name] = tidal_playlist_id
        total_added += len(added)
        total_failed += len(failed)

        status = f"✓ {len(added)}/{len(isrcs)} matched"
        if failed:
            status += f", {len(failed)} failed"
        console.print(f"  {playlist_name} — {status}")

    plan.save(input_file)

    console.print(f"\n[green]Done![/green] Synced {total_added} tracks to Tidal, {total_failed} failed.")
    if total_failed:
        console.print("[yellow]Run 'dj review' to see which tracks failed.[/yellow]")


@app.command()
def scan(
    directory: Path = typer.Argument(help="Path to local music directory (e.g., /Volumes/home/Music/Library)"),
    db: Path = typer.Option(None, "--db", help="Path to SQLite database (default: data/local-library.db)"),
    full: bool = typer.Option(False, "--full", help="Full re-scan (ignore existing entries)"),
) -> None:
    """Scan a local directory for audio files and index their metadata into SQLite."""
    from dj_cli.local_scanner import DEFAULT_DB_PATH, get_db_stats, scan_directory

    db_path = db or DEFAULT_DB_PATH

    console.print(f"Scanning [cyan]{directory}[/cyan] for audio files...")
    if not full:
        console.print("[dim]Incremental mode — skipping already indexed files[/dim]")

    def _progress(new, skip, path):
        name = path.name if path else "done"
        console.print(f"  [green]+{new}[/green] new, [dim]{skip} skipped[/dim] — {name}")

    conn, new_count, skipped = scan_directory(
        directory, db_path=db_path, incremental=not full, progress_callback=_progress,
    )
    conn.close()

    stats = get_db_stats(db_path)
    table = Table(title="Scan Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")
    table.add_row("New files indexed", str(new_count))
    table.add_row("Skipped (already indexed)", str(skipped))
    table.add_row("Total in database", str(stats["total"]))
    table.add_row("With title+artist tags", str(stats["with_tags"]))
    table.add_row("With ISRC", str(stats["with_isrc"]))
    for fmt, count in sorted(stats.get("formats", {}).items(), key=lambda x: -x[1]):
        table.add_row(f"Format: .{fmt}", str(count))
    console.print(table)

    console.print(f"Database: [green]{db_path}[/green]")


@app.command()
def match(
    input_file: Path = typer.Argument(help="Path to classified JSON"),
    db: Path = typer.Option(None, "--db", help="Path to SQLite library database (default: data/local-library.db)"),
    fuzzy_threshold: int = typer.Option(85, "--threshold", "-t", help="Fuzzy match threshold (0-100)"),
) -> None:
    """Match classified Spotify tracks to local audio files."""
    from dj_cli.local_scanner import DEFAULT_DB_PATH
    from dj_cli.matcher import match_tracks

    plan = EventPlan.load(input_file)

    db_path = db or DEFAULT_DB_PATH
    if not db_path.exists():
        console.print(f"[red]Library database not found: {db_path}[/red]")
        console.print("Run 'dj scan <directory>' first to create the local library index.")
        raise typer.Exit(1)

    console.print(f"Loaded [green]{len(plan.tracks)}[/green] tracks, matching against [cyan]{db_path}[/cyan]...")

    def _progress(i, total, track, result):
        if result.local_path:
            console.print(f"  [{i}/{total}] {track.display_name()} → [green]{result.method}[/green] ({result.score}%)")

    results = match_tracks(plan.tracks, db_path=db_path, fuzzy_threshold=fuzzy_threshold, progress_callback=_progress)

    # Summary
    by_method: dict[str, int] = {}
    for r in results:
        by_method[r.method] = by_method.get(r.method, 0) + 1

    table = Table(title="Match Results")
    table.add_column("Method", style="cyan")
    table.add_column("Tracks", justify="right", style="green")
    for method in ["isrc", "exact", "fuzzy", "none"]:
        count = by_method.get(method, 0)
        style = "red" if method == "none" else ""
        label = {"isrc": "ISRC match", "exact": "Artist+Title exact", "fuzzy": "Fuzzy match", "none": "Not found"}[method]
        table.add_row(label, f"[{style}]{count}[/{style}]" if style else str(count))
    console.print(table)

    # Save updated plan with local_path
    plan.save(input_file)
    console.print(f"Saved to [green]{input_file}[/green]")

    # Write missing report
    missing = [r.track for r in results if r.method == "none"]
    if missing:
        missing_file = input_file.with_suffix(".missing.txt")
        lines = [f"{t.display_name()} (ISRC: {t.isrc or 'none'})" for t in missing]
        missing_file.write_text("\n".join(lines))

        # Also write ISRC-only file
        isrc_file = input_file.with_suffix(".missing-isrcs.txt")
        isrcs = [t.isrc for t in missing if t.isrc]
        isrc_file.write_text("\n".join(isrcs))

        console.print(f"[yellow]{len(missing)} unmatched tracks written to {missing_file}[/yellow]")
        console.print(f"[yellow]{len(isrcs)} ISRCs written to {isrc_file}[/yellow]")


@app.command(name="analyze-mood")
def analyze_mood(
    input_file: Path = typer.Argument(help="Path to classified JSON (tracks must have local_path set)"),
) -> None:
    """Analyze audio features and assign mood to each locally matched track.

    Requires essentia — run via Docker if not installed locally.
    """
    from dj_cli.mood_analyzer import analyze_tracks

    plan = EventPlan.load(input_file)
    with_path = sum(1 for t in plan.tracks if t.local_path)
    console.print(f"Loaded [green]{len(plan.tracks)}[/green] tracks, [cyan]{with_path}[/cyan] have local files")

    if not with_path:
        console.print("[red]No tracks have local_path set. Run 'dj match' first.[/red]")
        raise typer.Exit(1)

    console.print("Analyzing audio features with essentia...")

    def _progress(i, total, track, mood, error):
        if error:
            console.print(f"  [{i}/{total}] {track.display_name()} → [red]error: {error}[/red]")
        elif mood:
            console.print(f"  [{i}/{total}] {track.display_name()} → [cyan]{mood}[/cyan]")

    analyzed = analyze_tracks(plan.tracks, progress_callback=_progress)
    console.print(f"\nAnalyzed [green]{analyzed}[/green] of {with_path} tracks")

    # Mood summary
    moods: dict[str, int] = {}
    for t in plan.tracks:
        if t.mood:
            moods[t.mood] = moods.get(t.mood, 0) + 1

    if moods:
        table = Table(title="Mood Distribution")
        table.add_column("Mood", style="cyan")
        table.add_column("Tracks", justify="right", style="green")
        for mood, count in sorted(moods.items(), key=lambda x: -x[1]):
            table.add_row(mood, str(count))
        console.print(table)

    plan.save(input_file)
    console.print(f"Saved to [green]{input_file}[/green]")


@app.command(name="build-library")
def build_library_cmd(
    input_file: Path = typer.Argument(help="Path to classified JSON with local_path and mood"),
    target: Path = typer.Option(Path.home() / "Music" / "Library", "--target", "-t", help="Target directory for the master library"),
) -> None:
    """Copy matched local files into a Genre/Mood/ folder structure."""
    from dj_cli.library_builder import build_library

    plan = EventPlan.load(input_file)
    candidates = sum(1 for t in plan.tracks if t.local_path)
    console.print(f"Loaded [green]{len(plan.tracks)}[/green] tracks, [cyan]{candidates}[/cyan] with local files")

    def _progress(i, total, track, dest_path):
        if i % 20 == 0 or i == total:
            console.print(f"  [{i}/{total}] {track.display_name()}")

    copied, skipped, missing = build_library(plan.tracks, target, progress_callback=_progress)

    table = Table(title="Library Build Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")
    table.add_row("Copied", str(copied))
    table.add_row("Already existed", str(skipped))
    table.add_row("Missing (no local file)", str(len(missing)))
    console.print(table)

    plan.save(input_file)
    console.print(f"Saved to [green]{input_file}[/green]")


@app.command(name="build-event")
def build_event_cmd(
    input_file: Path = typer.Argument(help="Path to classified JSON with local_path and mood"),
    output: Path = typer.Option(..., "--output", "-o", help="Output directory for event folder (e.g., ~/Music/Events/Wedding/)"),
) -> None:
    """Create an event folder with copies organized by Genre/Mood/."""
    from dj_cli.event_builder import build_event_folder

    plan = EventPlan.load(input_file)
    console.print(f"Loaded [green]{len(plan.tracks)}[/green] tracks")

    def _progress(i, total, track, target_path):
        if i % 20 == 0 or i == total:
            console.print(f"  [{i}/{total}] {track.display_name()}")

    created, skipped, missing = build_event_folder(plan.tracks, output, progress_callback=_progress)

    table = Table(title="Event Folder Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")
    table.add_row("Files copied", str(created))
    table.add_row("Already existed", str(skipped))
    table.add_row("Missing (no local file)", str(len(missing)))
    console.print(table)

    if missing:
        console.print(f"[yellow]{len(missing)} tracks written to {output / '_missing.txt'}[/yellow]")


@app.command()
def tag(
    input_file: Path = typer.Argument(help="Path to classified JSON with local_path"),
) -> None:
    """Write genre, mood, and era into audio file ID3/FLAC tags."""
    from dj_cli.tag_writer import tag_tracks

    plan = EventPlan.load(input_file)
    candidates = sum(1 for t in plan.tracks if t.local_path)
    console.print(f"Loaded [green]{len(plan.tracks)}[/green] tracks, [cyan]{candidates}[/cyan] with local files")

    def _progress(i, total, track, ok):
        status = "[green]ok[/green]" if ok else "[red]failed[/red]"
        if i % 20 == 0 or i == total or not ok:
            console.print(f"  [{i}/{total}] {track.display_name()} → {status}")

    success, failed = tag_tracks(plan.tracks, progress_callback=_progress)

    console.print(f"\n[green]Tagged {success} tracks[/green]", end="")
    if failed:
        console.print(f", [red]{failed} failed[/red]")
    else:
        console.print()

    plan.save(input_file)
    console.print(f"Saved to [green]{input_file}[/green]")


if __name__ == "__main__":
    app()
