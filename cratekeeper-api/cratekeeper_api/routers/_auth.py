"""Bearer-token auth dependency. Disabled in test_mode."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from cratekeeper_api.config import get_settings


def require_token(authorization: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if settings.test_mode or not settings.api_token:
        return
    expected = f"Bearer {settings.api_token}"
    if authorization != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid api token")


AuthDep = Depends(require_token)
