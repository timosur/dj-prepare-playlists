"""Pipeline step ordering — declarative DAG of job-type prerequisites.

A job for a given event can only be enqueued once every prerequisite job type
listed below has at least one ``succeeded`` ``JobRun`` for the same event.

Library-/global-scoped jobs (``scan-incremental``, ``scan-full``,
``build-library``) are intentionally absent: they have no event-scoped
prerequisites and may be run at any time.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

# job_type -> list of job types that must have at least one ``succeeded`` run
# (for the same event) before the job can be enqueued.
#
# Ordering follows the canonical pipeline documented in the
# ``prepare-event`` skill:
#   fetch → enrich → classify → match → analyze-mood → classify-tags
#         → apply-tags → build-event   (and undo-tags after apply-tags)
# Library-/global-scoped jobs (``scan-*``, ``build-library``) are intentionally
# absent — they have no event-scoped prerequisites.
PIPELINE_DEPENDENCIES: dict[str, list[str]] = {
    "refetch": ["fetch"],
    "enrich": ["fetch"],
    "classify": ["enrich"],
    "match": ["classify"],
    "analyze-mood": ["match"],
    "classify-tags": ["analyze-mood", "classify"],
    "apply-tags": ["classify-tags", "match"],
    "undo-tags": ["apply-tags"],
    "build-event": ["apply-tags"],
    "sync-spotify": ["fetch"],
    "sync-tidal": ["match"],
}


def prerequisites(job_type: str) -> list[str]:
    """Return the list of prerequisite job types for ``job_type``."""
    return list(PIPELINE_DEPENDENCIES.get(job_type, []))


def missing_prerequisites(db: Session, event_id: str, job_type: str) -> list[str]:
    """Return prerequisite job types not yet satisfied for ``event_id``.

    A prerequisite is considered satisfied when at least one ``JobRun`` of
    that type exists for the event with status ``succeeded``.
    """
    from cratekeeper_api.orm import JobRun

    needed = prerequisites(job_type)
    if not needed:
        return []
    rows = db.execute(
        select(JobRun.type).where(
            JobRun.event_id == event_id,
            JobRun.type.in_(needed),
            JobRun.status == "succeeded",
        )
    ).all()
    succeeded = {r[0] for r in rows}
    return [t for t in needed if t not in succeeded]
