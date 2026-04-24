"""Pytest fixtures: ephemeral postgres + alembic-migrated DB + httpx client.

Uses `docker run` directly rather than testcontainers to avoid the reaper hang
observed on Docker Desktop / Python 3.14 combo.
"""

from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import time
import uuid

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from cratekeeper_api import config as config_module
from cratekeeper_api import secrets_store
from cratekeeper_api.db import init_engine, session_scope
from cratekeeper_api.jobs.engine import reset_engine
from cratekeeper_api.seed import seed_all


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def postgres_container():
    name = f"ck-test-pg-{uuid.uuid4().hex[:8]}"
    port = _free_port()
    subprocess.check_call(
        [
            "docker", "run", "-d", "--rm", "--name", name,
            "-e", "POSTGRES_USER=dj",
            "-e", "POSTGRES_PASSWORD=dj",
            "-e", "POSTGRES_DB=djlib_test",
            "-p", f"{port}:5432",
            "postgres:16-alpine",
        ],
        stdout=subprocess.DEVNULL,
    )
    deadline = time.time() + 60
    last_err = None
    while time.time() < deadline:
        try:
            with psycopg.connect(
                host="127.0.0.1", port=port, user="dj", password="dj", dbname="djlib_test",
                connect_timeout=2,
            ) as conn:
                conn.execute("SELECT 1")
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(0.3)
    else:
        subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        raise RuntimeError(f"postgres did not become ready: {last_err}")
    try:
        yield {"name": name, "port": port}
    finally:
        subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


@pytest.fixture(scope="session")
def db_url(postgres_container) -> str:
    return f"postgresql+psycopg://dj:dj@127.0.0.1:{postgres_container['port']}/djlib_test"


@pytest.fixture(scope="session", autouse=True)
def _migrate(db_url):
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(scope="session", autouse=True)
def _configure_app(db_url, _migrate, tmp_path_factory):
    os.environ["CRATEKEEPER_DB_URL"] = db_url
    os.environ["CRATEKEEPER_TEST_MODE"] = "true"
    cfg_dir = tmp_path_factory.mktemp("ck-config")
    os.environ["CRATEKEEPER_CONFIG_DIR"] = str(cfg_dir)
    os.environ["CRATEKEEPER_DATA_DIR"] = str(tmp_path_factory.mktemp("ck-data"))
    config_module.reset_settings_cache()
    secrets_store.reset_fernet_cache()
    from cratekeeper_api.container import reset_container
    reset_container()
    init_engine(db_url)
    with session_scope() as db:
        seed_all(db)
    yield


@pytest.fixture(autouse=True)
def _truncate_between_tests(db_url):
    """Wipe mutable rows between tests; keep seed data."""
    yield
    engine = create_engine(db_url, future=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE event_tracks, event_builds, event_fetches, "
                "job_checkpoints, job_runs, playlist_sync_runs, audit_log, events RESTART IDENTITY CASCADE"
            )
        )
    reset_engine()


@pytest.fixture
def client():
    from cratekeeper_api.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
