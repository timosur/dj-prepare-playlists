"""Job type registry — handlers register here; engine looks them up.

Handler signature: `async def handler(ctx: JobContext) -> dict` returns the
final summary dict (persisted to `job_runs.summary`).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from cratekeeper_api.jobs.context import JobContext

JobHandler = Callable[[JobContext], Awaitable[dict]]


@dataclass
class JobSpec:
    type: str
    handler: JobHandler
    heavy: bool = False  # serialise via global heavy semaphore


_REGISTRY: dict[str, JobSpec] = {}


def register(job_type: str, *, heavy: bool = False):
    def decorator(fn: JobHandler) -> JobHandler:
        _REGISTRY[job_type] = JobSpec(type=job_type, handler=fn, heavy=heavy)
        return fn

    return decorator


def get(job_type: str) -> JobSpec | None:
    return _REGISTRY.get(job_type)


def all_types() -> list[str]:
    return sorted(_REGISTRY.keys())
