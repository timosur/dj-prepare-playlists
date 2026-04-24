"""Slug derivation — URL-safe, deterministic, lowercase."""

from __future__ import annotations

import re
import unicodedata


def slugify(text: str, *, max_len: int = 60) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if not text:
        text = "event"
    return text[:max_len]
