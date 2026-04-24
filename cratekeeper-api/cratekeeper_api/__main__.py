"""Entry point: `python -m cratekeeper_api` or `cratekeeper-api`."""

from __future__ import annotations

import uvicorn

from cratekeeper_api.config import get_settings


def main() -> None:
    s = get_settings()
    uvicorn.run("cratekeeper_api.main:app", host=s.bind_host, port=s.bind_port, reload=False)


if __name__ == "__main__":
    main()
