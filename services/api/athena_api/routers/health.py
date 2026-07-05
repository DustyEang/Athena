"""System health — everything the debug screen needs in one call."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from .. import __version__
from ..config import get_settings
from ..db import get_db
from ..plugins import get_plugin_registry
from ..providers import get_provider_registry
from ..voice.pipeline import voice_status

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"status": "ok", "version": __version__}


@router.get("/health/full")
async def health_full(conn: sqlite3.Connection = Depends(get_db)):
    env = get_settings()

    db_ok, db_detail = True, str(env.db_path)
    try:
        conn.execute("SELECT 1").fetchone()
    except sqlite3.Error as exc:
        db_ok, db_detail = False, str(exc)

    registry = get_plugin_registry()
    return {
        "status": "ok",
        "version": __version__,
        "env_mode": env.env,
        "database": {"ok": db_ok, "detail": db_detail},
        "providers": [vars(s) for s in await get_provider_registry().statuses()],
        "plugins": {
            "count": len(registry.plugins),
            "errors": {n: p.load_error for n, p in registry.plugins.items() if p.load_error},
        },
        "voice": voice_status(),
    }
