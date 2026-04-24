"""Job runtime context handed to handlers. Wraps SSE publishing + checkpoints
+ DB session factory + cancellation.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from cratekeeper_api.db import session_scope
from cratekeeper_api.jobs.sse import (
    event_channel,
    get_hub,
    log_channel,
    progress_channel,
)
from cratekeeper_api.orm import JobCheckpoint, JobRun


@dataclass
class JobContext:
    job_id: str
    event_id: str | None
    job_type: str
    params: dict[str, Any] = field(default_factory=dict)
    cancel_requested: bool = False

    # ----- SSE -----------------------------------------------------------
    def _ts(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z"

    def progress(self, i: int, total: int, *, phase: str | None = None, item: dict | None = None, result: dict | None = None) -> None:
        get_hub().publish(
            progress_channel(self.job_id),
            "progress",
            {
                "job_id": self.job_id,
                "ts": self._ts(),
                "i": i,
                "total": total,
                "phase": phase,
                "item": item,
                "result": result,
            },
        )
        with session_scope() as db:
            row = db.get(JobRun, self.job_id)
            if row:
                row.progress_i = i
                row.progress_total = total

    def log(self, msg: str, *, level: str = "info", src: str | None = None, extra: dict | None = None) -> None:
        payload = {
            "job_id": self.job_id,
            "ts": self._ts(),
            "level": level,
            "msg": msg,
            "src": src or self.job_type,
        }
        if extra:
            payload.update(extra)
        get_hub().publish(log_channel(self.job_id), "log", payload)

    def cost(self, *, input_tokens: int, output_tokens: int, cache_read: int, cache_write: int, est_usd: float) -> None:
        get_hub().publish(
            log_channel(self.job_id),
            "cost",
            {
                "job_id": self.job_id,
                "ts": self._ts(),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_read": cache_read,
                "cache_write": cache_write,
                "est_usd": round(est_usd, 4),
            },
        )

    def stage(self, stage: str, *, detail: str | None = None, summary: dict | None = None, error: dict | None = None) -> None:
        payload: dict[str, Any] = {"job_id": self.job_id, "ts": self._ts(), "stage": stage}
        if detail:
            payload["detail"] = detail
        if summary is not None:
            payload["summary"] = summary
        if error is not None:
            payload["error"] = error
        get_hub().publish(progress_channel(self.job_id), "stage", payload)
        if self.event_id:
            get_hub().publish(
                event_channel(self.event_id),
                "job_stage",
                {
                    "event_id": self.event_id,
                    "job_id": self.job_id,
                    "type": self.job_type,
                    "stage": stage,
                    "ts": self._ts(),
                },
            )

    # ----- Checkpoints ---------------------------------------------------
    def save_checkpoint(self, key: str, payload: dict[str, Any]) -> None:
        with session_scope() as db:
            stmt = pg_insert(JobCheckpoint).values(job_id=self.job_id, key=key, payload=payload)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_checkpoint_job_key",
                set_={"payload": stmt.excluded.payload},
            )
            db.execute(stmt)

    def completed_keys(self) -> set[str]:
        with session_scope() as db:
            rows = db.query(JobCheckpoint.key).filter(JobCheckpoint.job_id == self.job_id).all()
            return {r[0] for r in rows}

    def filter_remaining(self, items: Iterable[tuple[str, Any]]) -> list[tuple[str, Any]]:
        done = self.completed_keys()
        return [(k, v) for k, v in items if k not in done]

    @contextmanager
    def db_session(self):
        with session_scope() as s:
            yield s


def request_cancel(ctx: JobContext) -> None:
    ctx.cancel_requested = True
