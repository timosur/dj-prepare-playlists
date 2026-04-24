"""Milestone 4 — hardening tests: audit log, dry-run, undo-tags."""

from __future__ import annotations

import time
from pathlib import Path


def _wait_done(client, job_id: str, timeout: float = 10.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/v1/jobs/{job_id}").json()
        if body["status"] in ("succeeded", "failed", "cancelled"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish: {body}")


def _seed_succeeded_jobs(event_id: str, types: list[str]) -> None:
    """Insert dummy succeeded JobRun rows so dependency checks pass without
    actually executing heavy/IO-bound handlers."""
    from cratekeeper_api.db import session_scope
    from cratekeeper_api.orm import JobRun

    with session_scope() as db:
        for t in types:
            db.add(JobRun(event_id=event_id, type=t, params={}, status="succeeded", summary={}))


def test_audit_log_records_job_submit_and_settings_change(client, tmp_path: Path):
    ev = client.post("/api/v1/events", json={"name": "audit", "source_playlist_url": "test_wedding"}).json()
    job = client.post(f"/api/v1/events/{ev['id']}/jobs", json={"type": "fetch"}).json()
    _wait_done(client, job["id"])

    # Mutate fs-roots (a non-seeded settings entry) to generate a settings audit row
    r = client.put("/api/v1/settings/fs-roots", json={"roots": [str(tmp_path)]})
    assert r.status_code == 200

    rows = client.get("/api/v1/audit").json()
    actions = {r["action"] for r in rows}
    assert "job.submit" in actions
    assert "settings.fs_roots.update" in actions

    # Filter by job target
    job_rows = client.get(f"/api/v1/audit?target_kind=job&target_id={job['id']}").json()
    assert any(r["action"] == "job.submit" for r in job_rows)


def test_build_event_dry_run_does_not_touch_filesystem(client, tmp_path: Path):
    # Configure the tmp dir as an allowed FS root
    client.put("/api/v1/settings/fs-roots", json={"roots": [str(tmp_path)]})

    ev = client.post(
        "/api/v1/events",
        json={"name": "dry", "source_playlist_url": "test_wedding"},
    ).json()
    _wait_done(client, client.post(f"/api/v1/events/{ev['id']}/jobs", json={"type": "fetch"}).json()["id"])
    # build-event now requires the full chain through apply-tags. Seed the
    # intermediate steps as already-succeeded so we can exercise the dry_run
    # behavior in isolation.
    _seed_succeeded_jobs(
        ev["id"],
        ["enrich", "classify", "match", "analyze-mood", "classify-tags", "apply-tags"],
    )

    out = tmp_path / "dry-out"
    job = client.post(
        f"/api/v1/events/{ev['id']}/jobs",
        json={"type": "build-event", "params": {"output_dir": str(out), "dry_run": True}},
    ).json()
    body = _wait_done(client, job["id"])
    assert body["status"] == "succeeded"
    assert body["summary"]["dry_run"] is True
    # Nothing should have been created on disk
    assert not out.exists() or not any(out.rglob("*"))


def test_undo_tags_handler_runs_with_no_backups(client):
    """Smoke test: undo-tags is registered and tolerates an empty backup table."""
    ev = client.post("/api/v1/events", json={"name": "undo", "source_playlist_url": "test_wedding"}).json()
    eid = ev["id"]
    # undo-tags needs apply-tags. Seed the entire prerequisite chain as
    # succeeded so we can drive undo-tags in isolation.
    _wait_done(client, client.post(f"/api/v1/events/{eid}/jobs", json={"type": "fetch"}).json()["id"])
    _seed_succeeded_jobs(
        eid,
        ["enrich", "classify", "match", "analyze-mood", "classify-tags", "apply-tags"],
    )

    job = client.post(
        f"/api/v1/events/{eid}/jobs",
        json={"type": "undo-tags", "params": {"dry_run": True}},
    ).json()
    body = _wait_done(client, job["id"])
    assert body["status"] == "succeeded"
    assert body["summary"]["restored"] == 0
    assert body["summary"]["dry_run"] is True
