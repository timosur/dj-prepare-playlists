"""Settings router — secrets, FS roots, genre buckets, tag vocabularies."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from cratekeeper_api.db import get_db
from cratekeeper_api.orm import GenreBucketRow, Setting
from cratekeeper_api.routers._auth import AuthDep
from cratekeeper_api.schemas import (
    AnthropicSettingsIn,
    AnthropicSettingsOut,
    FsRootsIn,
    FsRootsOut,
    GenreBucketIn,
    GenreBucketOut,
    GenreBucketsReplace,
    TagVocabularies,
)
from cratekeeper_api.secrets_store import (
    get_setting,
    has_setting,
    set_setting,
)
from cratekeeper_api.security import get_allowed_roots, set_allowed_roots

router = APIRouter(prefix="/settings", tags=["settings"], dependencies=[AuthDep])


@router.get("")
async def get_settings_overview(db: Session = Depends(get_db)) -> dict:
    return {
        "anthropic_configured": has_setting(db, "anthropic_api_key"),
        "spotify_configured": has_setting(db, "spotify_refresh_token"),
        "tidal_configured": has_setting(db, "tidal_session"),
        "fs_roots": [str(p) for p in get_allowed_roots(db)],
    }


# --- anthropic ---


@router.get("/anthropic", response_model=AnthropicSettingsOut)
async def anthropic_get(db: Session = Depends(get_db)) -> AnthropicSettingsOut:
    model = get_setting(db, "anthropic_model") or "claude-sonnet-4-6"
    caching = get_setting(db, "anthropic_prompt_caching") or "true"
    return AnthropicSettingsOut(
        configured=has_setting(db, "anthropic_api_key"),
        model=model,
        prompt_caching=caching == "true",
    )


@router.put("/anthropic", response_model=AnthropicSettingsOut)
async def anthropic_put(body: AnthropicSettingsIn, db: Session = Depends(get_db)) -> AnthropicSettingsOut:
    if body.api_key:
        set_setting(db, "anthropic_api_key", body.api_key, is_secret=True)
    if body.model:
        set_setting(db, "anthropic_model", body.model)
    set_setting(db, "anthropic_prompt_caching", "true" if body.prompt_caching else "false")
    db.flush()
    from cratekeeper_api.services.audit import record
    record(
        action="settings.anthropic.update",
        target_kind="settings",
        payload={"key_changed": bool(body.api_key), "model": body.model, "prompt_caching": body.prompt_caching},
        db=db,
    )
    return await anthropic_get(db)


# --- fs roots ---


@router.get("/fs-roots", response_model=FsRootsOut)
async def fs_roots_get(db: Session = Depends(get_db)) -> FsRootsOut:
    return FsRootsOut(roots=[str(p) for p in get_allowed_roots(db)])


@router.put("/fs-roots", response_model=FsRootsOut)
async def fs_roots_put(body: FsRootsIn, db: Session = Depends(get_db)) -> FsRootsOut:
    roots = set_allowed_roots(db, body.roots)
    from cratekeeper_api.services.audit import record
    record(action="settings.fs_roots.update", target_kind="settings", payload={"roots": [str(p) for p in roots]}, db=db)
    return FsRootsOut(roots=[str(p) for p in roots])


# --- genre buckets ---


@router.get("/genre-buckets", response_model=list[GenreBucketOut])
async def buckets_get(db: Session = Depends(get_db)) -> list[GenreBucketOut]:
    rows = db.execute(select(GenreBucketRow).order_by(GenreBucketRow.sort_order)).scalars().all()
    return [
        GenreBucketOut(id=r.id, name=r.name, genre_tags=list(r.genre_tags), is_fallback=r.is_fallback, sort_order=r.sort_order)
        for r in rows
    ]


@router.put("/genre-buckets", response_model=list[GenreBucketOut])
async def buckets_put(body: GenreBucketsReplace, db: Session = Depends(get_db)) -> list[GenreBucketOut]:
    if not body.buckets:
        raise HTTPException(400, "at least one bucket required")
    db.query(GenreBucketRow).delete()
    db.flush()
    out: list[GenreBucketOut] = []
    for i, b in enumerate(body.buckets):
        row = GenreBucketRow(name=b.name, genre_tags=list(b.genre_tags), sort_order=i, is_fallback=b.is_fallback)
        db.add(row)
        db.flush()
        out.append(GenreBucketOut(id=row.id, name=row.name, genre_tags=list(row.genre_tags), is_fallback=row.is_fallback, sort_order=row.sort_order))
    from cratekeeper_api.services.audit import record
    record(
        action="settings.genre_buckets.update",
        target_kind="settings",
        payload={"count": len(out), "names": [b.name for b in out]},
        db=db,
    )
    return out


# --- tag vocabularies (read-only) ---


@router.get("/tag-vocabularies", response_model=TagVocabularies)
async def tag_vocab_get(db: Session = Depends(get_db)) -> TagVocabularies:
    raw = get_setting(db, "tag_vocabularies")
    data = json.loads(raw) if raw else {}
    return TagVocabularies(
        energy=data.get("energy", []),
        function=data.get("function", []),
        crowd=data.get("crowd", []),
        mood=data.get("mood", []),
    )


# --- OAuth health / re-auth -------------------------------------------------
# Re-uses the file-based credentials owned by spotify-mcp / tidal-mcp. The
# "relink" endpoints simply force a fresh client construction and report the
# resulting health, so a user can confirm credentials work after rotating them
# without restarting the API.


@router.get("/auth/spotify")
async def auth_spotify_status() -> dict:
    try:
        from cratekeeper.spotify_client import get_spotify_client
        sp = get_spotify_client()
        me = sp.current_user()
        return {"ok": True, "user": me.get("display_name") or me.get("id")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/auth/spotify/relink")
async def auth_spotify_relink() -> dict:
    return await auth_spotify_status()


@router.get("/auth/tidal")
async def auth_tidal_status() -> dict:
    try:
        from cratekeeper.tidal_client import get_tidal_session
        s = get_tidal_session()
        return {"ok": True, "user": getattr(s.user, "username", None) or str(s.user.id)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/auth/tidal/relink")
async def auth_tidal_relink() -> dict:
    return await auth_tidal_status()
