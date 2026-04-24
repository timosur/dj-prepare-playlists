"""Health + mount-precheck endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from cratekeeper_api.db import get_db
from cratekeeper_api.schemas import MountReport
from cratekeeper_api.security import mount_report

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/mounts", response_model=MountReport)
async def mounts(db: Session = Depends(get_db)) -> MountReport:
    return mount_report(db)
