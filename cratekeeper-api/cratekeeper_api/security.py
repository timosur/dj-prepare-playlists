"""Filesystem safety + mount pre-flight."""

from __future__ import annotations

import json
import os
from pathlib import Path

from sqlalchemy.orm import Session

from cratekeeper_api.config import get_settings
from cratekeeper_api.schemas import MountReport, MountStatus
from cratekeeper_api.secrets_store import get_setting, set_setting

DEFAULT_FS_ROOTS_KEY = "fs_roots"


class PathOutsideRootError(ValueError):
    """Raised when a user-supplied path escapes the configured roots."""


class MountNotReadyError(RuntimeError):
    def __init__(self, root: str, reason: str = "not_mounted"):
        super().__init__(f"{root}: {reason}")
        self.root = root
        self.reason = reason


def _expand(p: str) -> Path:
    return Path(os.path.expanduser(os.path.expandvars(p))).resolve()


def get_allowed_roots(db: Session) -> list[Path]:
    raw = get_setting(db, DEFAULT_FS_ROOTS_KEY)
    if raw:
        roots = json.loads(raw)
    else:
        s = get_settings()
        roots = ["/Volumes/Music", "~/Music/Library", str(s.data_dir)]
    return [_expand(r) for r in roots]


def set_allowed_roots(db: Session, roots: list[str]) -> list[Path]:
    set_setting(db, DEFAULT_FS_ROOTS_KEY, json.dumps(roots), is_secret=False)
    return [_expand(r) for r in roots]


def resolve_safe_path(user_path: str, db: Session) -> Path:
    """Resolve a user-supplied path and assert it lives under an allowed root."""
    target = _expand(user_path)
    for root in get_allowed_roots(db):
        try:
            target.relative_to(root)
            return target
        except ValueError:
            continue
    raise PathOutsideRootError(f"path {target} not under any allowed root")


def mount_report(db: Session, required_roots: list[str] | None = None) -> MountReport:
    roots = [_expand(r) for r in required_roots] if required_roots else get_allowed_roots(db)
    statuses = []
    for r in roots:
        exists = r.exists()
        readable = exists and os.access(r, os.R_OK)
        statuses.append(MountStatus(root=str(r), exists=exists, readable=readable))
    ok = all(s.readable for s in statuses)
    return MountReport(ok=ok, roots=statuses)


def precheck_or_raise(db: Session, required_roots: list[str]) -> None:
    report = mount_report(db, required_roots)
    if not report.ok:
        first_bad = next(s for s in report.roots if not s.readable)
        raise MountNotReadyError(first_bad.root, "not_mounted" if not first_bad.exists else "not_readable")
