def test_create_and_list_event(client):
    r = client.post(
        "/api/v1/events",
        json={"name": "Anna & Bob Wedding", "date": "2026-06-12", "source_playlist_url": "test_wedding"},
    )
    assert r.status_code == 201, r.text
    ev = r.json()
    assert ev["slug"] == "anna-bob-wedding"
    assert ev["build_mode"] == "copy"

    r = client.get("/api/v1/events")
    assert r.status_code == 200
    assert any(e["id"] == ev["id"] for e in r.json())


def test_slug_uniqueness(client):
    a = client.post("/api/v1/events", json={"name": "Same Name"}).json()
    b = client.post("/api/v1/events", json={"name": "Same Name"}).json()
    assert a["slug"] != b["slug"]


def test_quality_checks_empty_event(client):
    ev = client.post("/api/v1/events", json={"name": "Empty"}).json()
    r = client.get(f"/api/v1/events/{ev['id']}/quality-checks")
    assert r.status_code == 200
    body = r.json()
    assert body["overall"] in ("warn", "fail")
    names = {c["name"] for c in body["checks"]}
    assert {"tracks_classified", "match_rate", "audio_analysis", "llm_tags", "build_mode", "missing_tracks"} <= names


def test_delete_event_requires_confirm(client):
    ev = client.post("/api/v1/events", json={"name": "doomed"}).json()
    r = client.delete(f"/api/v1/events/{ev['id']}")
    assert r.status_code == 412
    r = client.delete(f"/api/v1/events/{ev['id']}?confirm=true")
    assert r.status_code == 204
