"""Audit log router — read-only listing of recent operations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from cratekeeper_api.db import get_db
from cratekeeper_api.orm import AuditLog
from cratekeeper_api.routers._auth import AuthDep

router = APIRouter(prefix="/audit", tags=["audit"], dependencies=[AuthDep])


@router.get("")
async def list_audit(
    limit: int = Query(100, ge=1, le=500),
    target_kind: str | None = None,
    target_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if target_kind:
        stmt = stmt.where(AuditLog.target_kind == target_kind)
    if target_id:
        stmt = stmt.where(AuditLog.target_id == target_id)
    rows = db.execute(stmt).scalars().all()
    return [
        {
            "id": r.id,
            "ts": r.ts.isoformat(),
            "actor": r.actor,
            "action": r.action,
            "target_kind": r.target_kind,
            "target_id": r.target_id,
            "payload": r.payload,
        }
        for r in rows
    ]
