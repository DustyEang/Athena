"""Plugin registry endpoints."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db import audit, get_db
from ..plugins import get_plugin_registry

router = APIRouter(tags=["plugins"])


class EnableRequest(BaseModel):
    enabled: bool


@router.get("/plugins")
def list_plugins(conn: sqlite3.Connection = Depends(get_db)):
    registry = get_plugin_registry()
    out = []
    for p in registry.plugins.values():
        out.append({
            "name": p.name,
            "display_name": p.display_name,
            "description": p.description,
            "version": p.version,
            "permission": p.permission,
            "placeholder": p.placeholder,
            "enabled": registry.is_enabled(conn, p.name),
            "load_error": p.load_error,
            "settings": registry.effective_settings(conn, p.name),
            "tools": [
                {"name": t.name, "description": t.description,
                 "permission": t.permission, "implemented": t.handler is not None}
                for t in p.tools.values()
            ],
        })
    return out


@router.post("/plugins/{name}/enabled")
def set_plugin_enabled(name: str, body: EnableRequest, conn: sqlite3.Connection = Depends(get_db)):
    registry = get_plugin_registry()
    if name not in registry.plugins:
        raise HTTPException(404, f"Unknown plugin '{name}'")
    registry.set_enabled(conn, name, body.enabled)
    audit(conn, "user", "plugin.enabled" if body.enabled else "plugin.disabled", name)
    return {"name": name, "enabled": body.enabled}


@router.post("/plugins/reload")
def reload_plugins():
    registry = get_plugin_registry()
    registry.reload()
    return {"loaded": list(registry.plugins)}
