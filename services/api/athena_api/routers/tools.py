"""Tool execution + confirmation workflow + activity feed."""
from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db import get_db, rows_to_dicts
from ..plugins import execute_tool, resolve_confirmation
from ..plugins.registry import ToolError

router = APIRouter(tags=["tools"])


class ToolExecuteRequest(BaseModel):
    plugin: str
    tool: str
    args: dict[str, Any] = {}
    workspace_id: str | None = None


class ConfirmRequest(BaseModel):
    approved: bool


@router.post("/tools/execute")
def tools_execute(body: ToolExecuteRequest, conn: sqlite3.Connection = Depends(get_db)):
    return execute_tool(conn, body.plugin, body.tool, body.args, workspace_id=body.workspace_id)


@router.post("/tools/confirm/{run_id}")
def tools_confirm(run_id: str, body: ConfirmRequest, conn: sqlite3.Connection = Depends(get_db)):
    try:
        return resolve_confirmation(conn, run_id, body.approved)
    except ToolError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/tools/runs")
def tool_runs(limit: int = 50, status: str | None = None, conn: sqlite3.Connection = Depends(get_db)):
    """Tool activity feed (also surfaces pending confirmations for the UI)."""
    q = "SELECT * FROM tool_runs"
    params: list[Any] = []
    if status:
        q += " WHERE status=?"
        params.append(status)
    q += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    return rows_to_dicts(conn.execute(q, params).fetchall())


@router.get("/tools/audit")
def audit_log(limit: int = 100, conn: sqlite3.Connection = Depends(get_db)):
    return rows_to_dicts(conn.execute(
        "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall())
