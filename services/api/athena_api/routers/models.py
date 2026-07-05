"""Model/provider endpoints: status, model list, usage history, routing preview."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..db import get_db, rows_to_dicts
from ..providers import get_provider_registry
from ..routing import route_request
from ..routing.costs import month_spend

router = APIRouter(tags=["models"])


@router.get("/models/providers")
async def provider_statuses():
    return [vars(s) for s in await get_provider_registry().statuses()]


@router.get("/models")
async def list_models():
    """All selectable models as 'provider:model' options for the UI."""
    options = []
    for status in await get_provider_registry().statuses():
        for model in status.models:
            options.append({
                "id": f"{status.name}:{model}", "provider": status.name,
                "model": model, "kind": status.kind, "available": status.available,
            })
    return options


class RoutePreviewRequest(BaseModel):
    message: str


@router.post("/models/route-preview")
async def route_preview(req: RoutePreviewRequest, conn: sqlite3.Connection = Depends(get_db)):
    """Dry-run routing: shows which model Athena WOULD pick and why."""
    d = await route_request(conn, req.message)
    return {
        "provider": d.provider, "model": d.model, "tier": d.tier,
        "task_type": d.task_type, "reason": d.reason,
        "needs_premium_confirmation": d.needs_premium_confirmation,
    }


@router.get("/models/usage")
def usage_history(limit: int = 100, conn: sqlite3.Connection = Depends(get_db)):
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM usage ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall())
    return {"month_spend_usd": round(month_spend(conn), 4), "history": rows}
