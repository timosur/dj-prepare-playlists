"""End-to-end vertical: create event → fetch → classify → classify-tags → quality."""

from __future__ import annotations

import time


def _wait_done(client, job_id: str, timeout: float = 10.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/api/v1/jobs/{job_id}")
        body = r.json()
        if body["status"] in ("succeeded", "failed", "cancelled"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish: {body}")


def test_full_vertical(client):
    # 1. Create event with a fixture playlist url
    ev = client.post(
        "/api/v1/events",
        json={"name": "Test Wedding", "source_playlist_url": "test_wedding"},
    ).json()
    eid = ev["id"]

    # 2. fetch
    r = client.post(f"/api/v1/events/{eid}/jobs", json={"type": "fetch", "params": {}})
    assert r.status_code == 202, r.text
    job = _wait_done(client, r.json()["id"])
    assert job["status"] == "succeeded"
    assert job["summary"]["track_count"] == 10
    assert job["summary"]["playlist_name"] == "Test Wedding Wishlist"

    # 3. event has 10 tracks
    tracks = client.get(f"/api/v1/events/{eid}/tracks").json()
    assert len(tracks) == 10

    # 3b. enrich (uses the mock MusicBrainz adapter; mostly a no-op for the
    # fixture but required by the pipeline DAG before classify).
    r = client.post(f"/api/v1/events/{eid}/jobs", json={"type": "enrich"})
    job = _wait_done(client, r.json()["id"])
    assert job["status"] == "succeeded", job

    # 4. classify (with min_bucket_size=1 so we keep every bucket as-is for assertion clarity)
    r = client.post(
        f"/api/v1/events/{eid}/jobs",
        json={"type": "classify", "params": {"min_bucket_size": 1}},
    )
    job = _wait_done(client, r.json()["id"])
    assert job["status"] == "succeeded", job
    counts = job["summary"]["bucket_counts"]
    # The fixture has clear genre signals — Schlager + House should show up
    assert "Schlager" in counts
    assert sum(counts.values()) == 10

    # 5. tracks now have buckets
    tracks = client.get(f"/api/v1/events/{eid}/tracks").json()
    assert all(t["bucket"] for t in tracks)

    # 6. classify-tags requires analyze-mood (per pipeline DAG). The audio
    # analyzer needs essentia + real files, so seed a succeeded analyze-mood
    # row directly to satisfy the dependency.
    from cratekeeper_api.db import session_scope
    from cratekeeper_api.orm import JobRun

    with session_scope() as db:
        db.add(JobRun(event_id=eid, type="analyze-mood", status="succeeded", params={}, summary={}))

    # 6. classify-tags (mocked anthropic)
    r = client.post(f"/api/v1/events/{eid}/jobs", json={"type": "classify-tags", "params": {}})
    job = _wait_done(client, r.json()["id"])
    assert job["status"] == "succeeded", job
    assert job["summary"]["tagged"] == 10
    assert job["summary"]["est_usd"] >= 0

    # 7. tracks now have energy/function/crowd/mood
    tracks = client.get(f"/api/v1/events/{eid}/tracks").json()
    assert all(t["energy"] for t in tracks)
    assert all(t["function"] for t in tracks)

    # 8. quality endpoint runs
    qr = client.get(f"/api/v1/events/{eid}/quality-checks").json()
    assert qr["overall"] in ("pass", "warn", "fail")  # match_rate is 0 → fail expected
    by_name = {c["name"]: c for c in qr["checks"]}
    assert by_name["llm_tags"]["status"] == "pass"
    assert by_name["tracks_classified"]["status"] == "pass"
    assert by_name["match_rate"]["status"] == "fail"  # nothing matched (no scan run)


def test_bulk_rebucket(client):
    ev = client.post("/api/v1/events", json={"name": "bulk", "source_playlist_url": "test_wedding"}).json()
    fetch_job = client.post(f"/api/v1/events/{ev['id']}/jobs", json={"type": "fetch"}).json()
    _wait_done(client, fetch_job["id"])
    tracks = client.get(f"/api/v1/events/{ev['id']}/tracks").json()
    ids = [t["id"] for t in tracks[:3]]
    r = client.post(
        f"/api/v1/events/{ev['id']}/tracks/bulk",
        json={"track_ids": ids, "action": "rebucket", "bucket": "Custom Bucket"},
    )
    assert r.status_code == 200
    assert r.json() == 3
    after = client.get(f"/api/v1/events/{ev['id']}/tracks").json()
    custom = [t for t in after if t["bucket"] == "Custom Bucket"]
    assert len(custom) == 3


def test_refetch_diff(client):
    """Use the spotify mock with a custom fixture set to exercise add/remove diff."""
    from cratekeeper_api.container import set_spotify
    from cratekeeper_api.integrations.spotify import MockSpotifyAdapter, SpotifyTrackData

    base = [
        SpotifyTrackData(id="sp_a", name="A", artists=["X"], artist_ids=["x"], album=None, duration_ms=200_000),
        SpotifyTrackData(id="sp_b", name="B", artists=["X"], artist_ids=["x"], album=None, duration_ms=200_000),
    ]
    after = [
        SpotifyTrackData(id="sp_b", name="B", artists=["X"], artist_ids=["x"], album=None, duration_ms=200_000),
        SpotifyTrackData(id="sp_c", name="C", artists=["X"], artist_ids=["x"], album=None, duration_ms=200_000),
    ]

    set_spotify(MockSpotifyAdapter({"plist": ("Plist", base)}))
    ev = client.post("/api/v1/events", json={"name": "diff", "source_playlist_url": "plist"}).json()
    fetch1 = client.post(f"/api/v1/events/{ev['id']}/jobs", json={"type": "fetch"}).json()
    _wait_done(client, fetch1["id"])

    set_spotify(MockSpotifyAdapter({"plist": ("Plist", after)}))
    refetch = client.post(f"/api/v1/events/{ev['id']}/jobs", json={"type": "refetch"}).json()
    job = _wait_done(client, refetch["id"])
    assert job["summary"] == {"added": 1, "removed": 1, "unchanged": 1, "playlist_name": "Plist"}
