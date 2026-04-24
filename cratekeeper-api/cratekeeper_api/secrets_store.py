"""Secrets storage — Fernet-encrypted values in the `settings` table."""

from __future__ import annotations

import base64
import os
from functools import lru_cache

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from cratekeeper_api.config import get_settings
from cratekeeper_api.orm import Setting


def _load_or_create_key() -> bytes:
    s = get_settings()
    if s.secret_key:
        return s.secret_key.encode() if len(s.secret_key) == 44 else base64.urlsafe_b64encode(s.secret_key.encode()[:32].ljust(32, b"\0"))
    key_path = s.config_dir / "secret.key"
    if key_path.exists():
        return key_path.read_bytes().strip()
    key = Fernet.generate_key()
    key_path.write_bytes(key)
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass
    return key


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    return Fernet(_load_or_create_key())


def reset_fernet_cache() -> None:
    _fernet.cache_clear()


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()


def set_setting(db: Session, key: str, value: str | None, is_secret: bool = False) -> None:
    row = db.get(Setting, key)
    stored = encrypt(value) if (value is not None and is_secret) else value
    if row is None:
        db.add(Setting(key=key, value=stored, is_secret=is_secret))
    else:
        row.value = stored
        row.is_secret = is_secret


def get_setting(db: Session, key: str, default: str | None = None) -> str | None:
    row = db.get(Setting, key)
    if row is None or row.value is None:
        return default
    if row.is_secret:
        try:
            return decrypt(row.value)
        except Exception:
            return None
    return row.value


def has_setting(db: Session, key: str) -> bool:
    row = db.get(Setting, key)
    return row is not None and row.value is not None
