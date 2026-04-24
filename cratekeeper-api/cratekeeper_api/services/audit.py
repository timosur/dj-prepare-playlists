"""Audit log helpers — write rows to the `audit_log` table.

The table is created in the initial Alembic migration. This module is the
single funnel for any "who did what" event: job submit/cancel/resume,
destructive actions (apply-tags / undo-tags / build-event / build-library /
sync-*), settings mutations, FS-root or genre-bucket changes.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from cratekeeper_api.db import session_scope
from cratekeeper_api.orm import AuditLog


def record(
    action: str,
    *,
    target_kind: str | None = None,
    target_id: str | None = None,
    payload: dict[str, Any] | None = None,
    actor: str = "local",
    db: Session | None = None,
) -> None:
    row = AuditLog(
        actor=actor,
        action=action,
        target_kind=target_kind,
        target_id=target_id,
        payload=payload or {},
    )
    if db is not None:
        db.add(row)
        return
    with session_scope() as s:
        s.add(row)
