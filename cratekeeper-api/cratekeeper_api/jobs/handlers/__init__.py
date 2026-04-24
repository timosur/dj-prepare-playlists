"""Job handlers — register here, picked up by `cratekeeper_api.jobs.registry`.

Importing this package triggers `register(...)` decorators on each handler.
"""

from cratekeeper_api.jobs.handlers import analyze as _analyze  # noqa: F401
from cratekeeper_api.jobs.handlers import apply_tags as _apply_tags  # noqa: F401
from cratekeeper_api.jobs.handlers import build as _build  # noqa: F401
from cratekeeper_api.jobs.handlers import classify as _classify  # noqa: F401
from cratekeeper_api.jobs.handlers import classify_tags as _classify_tags  # noqa: F401
from cratekeeper_api.jobs.handlers import enrich as _enrich  # noqa: F401
from cratekeeper_api.jobs.handlers import fetch as _fetch  # noqa: F401
from cratekeeper_api.jobs.handlers import match as _match  # noqa: F401
from cratekeeper_api.jobs.handlers import refetch as _refetch  # noqa: F401
from cratekeeper_api.jobs.handlers import scan as _scan  # noqa: F401
from cratekeeper_api.jobs.handlers import sync as _sync  # noqa: F401
from cratekeeper_api.jobs.handlers import undo_tags as _undo_tags  # noqa: F401
