"""Anthropic LLM tag classifier.

Live client uses the `anthropic` Python SDK with prompt caching: the fixed
system instruction + tag vocabularies are sent with `cache_control={"type":
"ephemeral"}` so subsequent chunks within the 5-minute cache window get
charged at the cache-read rate (~10x cheaper than fresh input).

The mock returns deterministic tags so the rest of the pipeline can be
exercised without network or API spend.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol


@dataclass
class TagResult:
    spotify_id: str
    energy: str
    function: list[str]
    crowd: list[str]
    mood: list[str]
    genre_suggestion: str | None = None


@dataclass
class ClassifyTagsResponse:
    results: list[TagResult]
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int

    def est_usd(self) -> float:
        # Sonnet pricing: $3/M input, $15/M output, $0.30/M cache read, $3.75/M cache write.
        return (
            self.input_tokens * 3.0
            + self.output_tokens * 15.0
            + self.cache_read_tokens * 0.30
            + self.cache_write_tokens * 3.75
        ) / 1_000_000


class AnthropicTagClient(Protocol):
    async def classify_tags(self, tracks: list[dict], model: str, prompt_caching: bool) -> ClassifyTagsResponse: ...


# --------------------------------------------------------------------------- live

_SYSTEM_PROMPT = """You are a wedding/event DJ assistant tagging tracks for crate organisation.

For each input track, assign the following dimensions. Use ONLY values from the
allowed vocabularies; multi-value dimensions return arrays.

Vocabularies:
- energy (single string): "low" | "mid" | "high"
- function (array, 1-3): ["warmup","floorfiller","singalong","bridge","closer","dinner"]
- crowd (array, 1-2): ["younger","mixed-age","older"]
- mood (array, 1-3): ["nostalgic","euphoric","emotional","feelgood","romantic","dark"]
- genre_suggestion (optional string): suggest a different genre bucket only if the
  current bucket assignment is clearly wrong; otherwise omit the field.

Return STRICT JSON in the form:
{"results":[{"spotify_id":"...", "energy":"...", "function":[...], "crowd":[...], "mood":[...], "genre_suggestion":"..."}, ...]}

Do NOT include any prose, markdown, or commentary. JSON only."""


class LiveAnthropicTagClient:
    """Real Anthropic client. The API key is injected at construction time."""

    def __init__(self, api_key: str) -> None:
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=api_key)

    async def classify_tags(self, tracks: list[dict], model: str, prompt_caching: bool) -> ClassifyTagsResponse:
        user_block = "Tag these tracks:\n" + json.dumps(tracks, ensure_ascii=False)

        system_blocks: list[dict] = [{"type": "text", "text": _SYSTEM_PROMPT}]
        if prompt_caching:
            system_blocks[0]["cache_control"] = {"type": "ephemeral"}

        msg = await self._client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_blocks,
            messages=[{"role": "user", "content": user_block}],
        )

        # Extract first text block
        text = ""
        for block in msg.content:
            if getattr(block, "type", None) == "text":
                text = block.text
                break

        results = _parse_results(text, tracks)

        usage = msg.usage
        return ClassifyTagsResponse(
            results=results,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
        )


def _parse_results(text: str, tracks: list[dict]) -> list[TagResult]:
    """Best-effort JSON parser — strips markdown fences if the model added any."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback: locate the first {...} block
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        data = json.loads(match.group(0)) if match else {"results": []}

    raw = data.get("results", [])
    out: list[TagResult] = []
    seen: set[str] = set()
    for r in raw:
        sid = r.get("spotify_id")
        if not sid or sid in seen:
            continue
        seen.add(sid)
        out.append(
            TagResult(
                spotify_id=sid,
                energy=str(r.get("energy") or "mid"),
                function=list(r.get("function") or []),
                crowd=list(r.get("crowd") or []),
                mood=list(r.get("mood") or []),
                genre_suggestion=r.get("genre_suggestion") or None,
            )
        )
    return out


# --------------------------------------------------------------------------- mock


class MockAnthropicTagClient:
    """Deterministic mock — rotates through fixed tag combinations."""

    def __init__(self, cache_hit: bool = False) -> None:
        self._cache_hit = cache_hit

    async def classify_tags(self, tracks: list[dict], model: str, prompt_caching: bool) -> ClassifyTagsResponse:
        rotations = [
            ("high", ["floorfiller"], ["mixed-age"], ["euphoric"]),
            ("mid", ["singalong"], ["older"], ["nostalgic"]),
            ("low", ["bridge"], ["mixed-age"], ["emotional"]),
            ("high", ["closer"], ["younger"], ["feelgood"]),
        ]
        results = []
        for i, t in enumerate(tracks):
            energy, fn, crowd, mood = rotations[i % len(rotations)]
            results.append(
                TagResult(
                    spotify_id=t["spotify_id"],
                    energy=energy,
                    function=fn,
                    crowd=crowd,
                    mood=mood,
                    genre_suggestion=None,
                )
            )
        n = len(tracks)
        return ClassifyTagsResponse(
            results=results,
            input_tokens=200 * n + (0 if self._cache_hit else 1500),
            output_tokens=80 * n,
            cache_read_tokens=1500 if self._cache_hit else 0,
            cache_write_tokens=0 if self._cache_hit else 1500,
        )


def get_anthropic_tag_client(use_mock: bool = False, api_key: str | None = None) -> AnthropicTagClient:
    """Factory.

    - `use_mock=True` → MockAnthropicTagClient.
    - else requires a non-empty `api_key`; raises if missing.
    """
    if use_mock:
        return MockAnthropicTagClient()
    if not api_key:
        raise RuntimeError("Anthropic API key not configured. Set it via PUT /api/v1/settings/anthropic.")
    return LiveAnthropicTagClient(api_key=api_key)
