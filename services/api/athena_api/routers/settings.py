"""User-editable settings (stored in DB so the UI can change them live).

Env-level config (API keys, ports) is intentionally NOT writable here —
secrets stay in .env / environment variables. GET exposes only whether a
key is configured, never the key itself.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..config import get_settings as env_settings
from ..db import audit, get_db, get_setting, set_setting

router = APIRouter(tags=["settings"])

DEFAULTS: dict[str, Any] = {
    "theme": "dark",
    "orb_behavior": "ambient",            # ambient | minimal | off
    "default_model": "",                  # "" = auto-route; else "provider:model"
    "task_mode": "balanced",              # cheap | balanced | max_power
    "ask_before_premium": True,
    "budget_monthly_usd": 20.0,
    "memory_mode": "ask",                 # off | ask | auto_important | project_only | full
    "agent_tools_enabled": True,          # let the model call tools mid-chat
    "voice_enabled": False,
    "wake_word_enabled": False,
    "server_mode": "local",               # local | server_assisted | cloud_orchestrated
    "remote_server_url": "",
    "debug_mode": False,
    "logs_retention_days": 14,
    "default_workspace_id": "",
    "app_launcher_allowlist": ["notepad", "calc", "explorer", "mspaint"],
}


class SettingsUpdate(BaseModel):
    values: dict[str, Any]


@router.get("/settings")
def get_all_settings(conn: sqlite3.Connection = Depends(get_db)):
    values = {k: get_setting(conn, k, default) for k, default in DEFAULTS.items()}
    env = env_settings()
    values["_env"] = {  # read-only env status for the UI (no secrets)
        "mode": env.env,
        "ollama_url": env.ollama_url,
        "fable5_configured": bool(env.fable5_api_key),
        "server_url_configured": bool(env.server_url),
    }
    return values


@router.put("/settings")
def update_settings(body: SettingsUpdate, conn: sqlite3.Connection = Depends(get_db)):
    applied = {}
    for key, value in body.values.items():
        if key not in DEFAULTS:
            continue  # unknown keys ignored; keeps DB clean
        set_setting(conn, key, value)
        applied[key] = value
    if applied:
        audit(conn, "user", "settings.update", ", ".join(applied))
    return {"applied": applied}
