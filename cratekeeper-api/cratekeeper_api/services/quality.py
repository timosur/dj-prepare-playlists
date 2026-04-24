"""Quality checks service. Aggregates the skill's pre-flight panel into one
structured response.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from cratekeeper_api.orm import Event, EventTrack
from cratekeeper_api.schemas import QualityCheck, QualityReport


def compute(db: Session, event_id: str) -> QualityReport:
    ev = db.get(Event, event_id)
    if ev is None:
        raise KeyError(event_id)

    tracks = db.execute(select(EventTrack).where(EventTrack.event_id == event_id)).scalars().all()
    n = len(tracks)
    checks: list[QualityCheck] = []

    # 1. All tracks accounted for
    classified = sum(1 for t in tracks if t.bucket)
    checks.append(
        QualityCheck(
            name="tracks_classified",
            status="pass" if classified == n and n > 0 else ("warn" if n > 0 else "fail"),
            detail=f"{classified}/{n} tracks have a bucket",
            metric=classified,
        )
    )

    # 2. Match rate ≥ 50%
    matched = sum(1 for t in tracks if t.match_status in ("isrc", "exact", "fuzzy"))
    rate = matched / n if n else 0.0
    checks.append(
        QualityCheck(
            name="match_rate",
            status="pass" if rate >= 0.5 else ("warn" if rate >= 0.3 else "fail"),
            detail=f"{matched}/{n} matched ({rate:.0%})",
            metric=round(rate, 3),
        )
    )

    # 3. Audio analysis complete
    analyzed = sum(1 for t in tracks if t.bpm is not None)
    checks.append(
        QualityCheck(
            name="audio_analysis",
            status="pass" if analyzed == matched else ("warn" if analyzed > 0 else "fail"),
            detail=f"{analyzed}/{matched} matched tracks have BPM",
            metric=analyzed,
        )
    )

    # 4. LLM tags assigned
    tagged = sum(1 for t in tracks if t.energy)
    checks.append(
        QualityCheck(
            name="llm_tags",
            status="pass" if tagged == n and n > 0 else ("warn" if tagged > 0 else "fail"),
            detail=f"{tagged}/{n} tracks have LLM tags",
            metric=tagged,
        )
    )

    # 5. Symlink warning
    if ev.build_mode == "symlink":
        checks.append(
            QualityCheck(
                name="build_mode",
                status="warn",
                detail="Event folder uses symlinks; not portable to external drives.",
            )
        )
    else:
        checks.append(QualityCheck(name="build_mode", status="pass", detail="copy mode"))

    # 6. Missing tracks listed (informational)
    missing = sum(1 for t in tracks if t.match_status == "missing")
    checks.append(
        QualityCheck(
            name="missing_tracks",
            status="pass" if missing == 0 else "warn",
            detail=f"{missing} missing track(s)",
            metric=missing,
        )
    )

    overall: str = "pass"
    if any(c.status == "fail" for c in checks):
        overall = "fail"
    elif any(c.status == "warn" for c in checks):
        overall = "warn"
    return QualityReport(overall=overall, checks=checks)
