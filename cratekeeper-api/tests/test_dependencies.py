"""Tests for pipeline-step dependency enforcement at enqueue time."""

from __future__ import annotations

import time


def _wait_done(client, job_id: str, timeout: float = 10.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/v1/jobs/{job_id}").json()
        if body["status"] in ("succeeded", "failed", "cancelled"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish: {body}")


def test_dependencies_endpoint_returns_dag(client):
    deps = client.get("/api/v1/jobs/dependencies").json()
    # canonical pipeline (per the prepare-event skill):
    #   fetch → enrich → classify → match → analyze-mood → classify-tags
    #         → apply-tags → build-event   (undo-tags after apply-tags)
    assert deps["enrich"] == ["fetch"]
    assert deps["classify"] == ["enrich"]
    assert deps["match"] == ["classify"]
    assert deps["analyze-mood"] == ["match"]
    assert set(deps["classify-tags"]) == {"analyze-mood", "classify"}
    assert set(deps["apply-tags"]) == {"classify-tags", "match"}
    assert deps["undo-tags"] == ["apply-tags"]
    assert deps["build-event"] == ["apply-tags"]
    assert deps["sync-tidal"] == ["match"]
    # fetch itself has no prereqs (not present in the map)
    assert "fetch" not in deps


def test_classify_blocked_until_fetch_succeeds(client):
    ev = client.post(
        "/api/v1/events",
        json={"name": "deps", "source_playlist_url": "test_wedding"},
    ).json()
    eid = ev["id"]

    # classify before fetch -> 409 (mentions enrich now, the immediate prereq)
    r = client.post(f"/api/v1/events/{eid}/jobs", json={"type": "classify"})
    assert r.status_code == 409, r.text
    assert "enrich" in r.json()["detail"]

    # run fetch + enrich
    job = client.post(f"/api/v1/events/{eid}/jobs", json={"type": "fetch"}).json()
    _wait_done(client, job["id"])
    job = client.post(f"/api/v1/events/{eid}/jobs", json={"type": "enrich"}).json()
    _wait_done(client, job["id"])

    # now classify is allowed
    r = client.post(
        f"/api/v1/events/{eid}/jobs",
        json={"type": "classify", "params": {"min_bucket_size": 1}},
    )
    assert r.status_code == 202, r.text


def test_apply_tags_requires_match_and_classify(client):
    ev = client.post(
        "/api/v1/events",
        json={"name": "deps2", "source_playlist_url": "test_wedding"},
    ).json()
    eid = ev["id"]

    # fetch only — apply-tags still missing the rest of the chain
    job = client.post(f"/api/v1/events/{eid}/jobs", json={"type": "fetch"}).json()
    _wait_done(client, job["id"])

    r = client.post(f"/api/v1/events/{eid}/jobs", json={"type": "apply-tags"})
    assert r.status_code == 409
    detail = r.json()["detail"]
    # apply-tags directly requires classify-tags + match
    assert "classify-tags" in detail
    assert "match" in detail


def test_match_blocked_until_classify(client):
    ev = client.post(
        "/api/v1/events",
        json={"name": "match-deps", "source_playlist_url": "test_wedding"},
    ).json()
    eid = ev["id"]
    _wait_done(client, client.post(f"/api/v1/events/{eid}/jobs", json={"type": "fetch"}).json()["id"])
    _wait_done(client, client.post(f"/api/v1/events/{eid}/jobs", json={"type": "enrich"}).json()["id"])

    # match before classify -> 409
    r = client.post(f"/api/v1/events/{eid}/jobs", json={"type": "match"})
    assert r.status_code == 409
    assert "classify" in r.json()["detail"]

    # after classify, match is allowed
    _wait_done(
        client,
        client.post(
            f"/api/v1/events/{eid}/jobs",
            json={"type": "classify", "params": {"min_bucket_size": 1}},
        ).json()["id"],
    )
    r = client.post(f"/api/v1/events/{eid}/jobs", json={"type": "match"})
    assert r.status_code == 202, r.text


def test_build_event_requires_apply_tags(client):
    ev = client.post(
        "/api/v1/events",
        json={"name": "be-deps", "source_playlist_url": "test_wedding"},
    ).json()
    eid = ev["id"]
    _wait_done(client, client.post(f"/api/v1/events/{eid}/jobs", json={"type": "fetch"}).json()["id"])

    r = client.post(f"/api/v1/events/{eid}/jobs", json={"type": "build-event"})
    assert r.status_code == 409
    assert "apply-tags" in r.json()["detail"]


def test_global_jobs_have_no_event_prereqs(client):
    # scan-incremental is library-scoped and may always be enqueued without an event.
    # We don't run it (heavy), just verify dependencies map omits it.
    deps = client.get("/api/v1/jobs/dependencies").json()
    assert "scan-incremental" not in deps
    assert "scan-full" not in deps
    assert "build-library" not in deps
