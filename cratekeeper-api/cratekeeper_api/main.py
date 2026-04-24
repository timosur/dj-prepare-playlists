"""FastAPI application factory + lifespan."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cratekeeper_api import jobs as _jobs_pkg  # noqa: F401  ensures engine importable
from cratekeeper_api.config import get_settings
from cratekeeper_api.db import init_engine, session_scope
from cratekeeper_api.jobs.handlers import (  # noqa: F401  registers handlers
    analyze,
    apply_tags,
    build,
    classify,
    classify_tags,
    fetch,
    match,
    refetch,
    scan,
    sync,
    undo_tags,
)
from cratekeeper_api.routers import (
    audit as audit_router,
    events,
    health,
    jobs,
    library as library_router,
    settings as settings_router,
)
from cratekeeper_api.seed import seed_all

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    init_engine(s.db_url)
    try:
        with session_scope() as db:
            seed_all(db)
    except Exception:
        log.warning("seed_all failed (db may not be migrated yet)", exc_info=True)
    yield
    from cratekeeper_api.jobs.engine import get_engine
    await get_engine().shutdown()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="Cratekeeper API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(events.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")
    app.include_router(settings_router.router, prefix="/api/v1")
    app.include_router(library_router.router, prefix="/api/v1")
    app.include_router(audit_router.router, prefix="/api/v1")
    return app


app = create_app()
