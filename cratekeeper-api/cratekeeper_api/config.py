"""Application configuration."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Backend settings — read from env, then `.env`."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="CRATEKEEPER_", extra="ignore")

    db_url: str = Field(default="postgresql+psycopg://dj:dj@localhost:5432/djlib")
    api_token: str | None = Field(default=None)
    secret_key: str | None = Field(default=None)
    data_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2] / "data")
    config_dir: Path = Field(default_factory=lambda: Path.home() / ".config" / "cratekeeper")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://127.0.0.1:5173", "http://localhost:5173"])
    bind_host: str = Field(default="127.0.0.1")
    bind_port: int = Field(default=8765)
    # Test mode disables auth + persists secrets in plaintext (Fernet still used,
    # but the key is generated fresh per-process if missing — safe for ephemeral tests).
    test_mode: bool = Field(default=False)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    s.config_dir.mkdir(parents=True, exist_ok=True)
    s.data_dir.mkdir(parents=True, exist_ok=True)
    return s


def reset_settings_cache() -> None:
    """Used by tests after mutating env vars."""
    get_settings.cache_clear()
