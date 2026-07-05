"""Workspace endpoints — projects Athena knows about."""
from __future__ import annotations

import json
import sqlite3
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db import audit, get_db, new_id, rows_to_dicts

router = APIRouter(tags=["workspaces"])

_JSON_FIELDS = ("model_prefs", "tool_settings")


def _decode(ws: dict) -> dict:
    for f in _JSON_FIELDS:
        try:
            ws[f] = json.loads(ws.get(f) or "{}")
        except json.JSONDecodeError:
            ws[f] = {}
    return ws


class WorkspaceCreate(BaseModel):
    name: str
    description: str = ""
    root_path: str = ""


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    root_path: str | None = None
    goals: str | None = None
    roadmap: str | None = None
    notes: str | None = None
    model_prefs: dict | None = None
    tool_settings: dict | None = None


@router.get("/workspaces")
def list_workspaces(conn: sqlite3.Connection = Depends(get_db)):
    return [_decode(w) for w in rows_to_dicts(
        conn.execute("SELECT * FROM workspaces ORDER BY name").fetchall()
    )]


@router.post("/workspaces")
def create_workspace(body: WorkspaceCreate, conn: sqlite3.Connection = Depends(get_db)):
    ws_id = new_id()
    try:
        conn.execute(
            "INSERT INTO workspaces(id,name,description,root_path,created_at) VALUES(?,?,?,?,?)",
            (ws_id, body.name, body.description, body.root_path, time.time()),
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(409, f"Workspace '{body.name}' already exists") from exc
    audit(conn, "user", "workspace.create", body.name)
    return _decode(dict(conn.execute("SELECT * FROM workspaces WHERE id=?", (ws_id,)).fetchone()))


@router.get("/workspaces/{ws_id}")
def get_workspace(ws_id: str, conn: sqlite3.Connection = Depends(get_db)):
    row = conn.execute("SELECT * FROM workspaces WHERE id=?", (ws_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Workspace not found")
    ws = _decode(dict(row))
    # Activity: recent memories + tool runs give a lightweight activity log
    ws["recent_memories"] = rows_to_dicts(conn.execute(
        "SELECT * FROM memories WHERE workspace_id=? ORDER BY updated_at DESC LIMIT 10",
        (ws_id,),
    ).fetchall())
    return ws


@router.patch("/workspaces/{ws_id}")
def update_workspace(ws_id: str, body: WorkspaceUpdate, conn: sqlite3.Connection = Depends(get_db)):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return get_workspace(ws_id, conn)
    for f in _JSON_FIELDS:
        if f in updates:
            updates[f] = json.dumps(updates[f])
    sets = ", ".join(f"{k}=?" for k in updates)
    cur = conn.execute(f"UPDATE workspaces SET {sets} WHERE id=?", (*updates.values(), ws_id))
    if cur.rowcount == 0:
        raise HTTPException(404, "Workspace not found")
    audit(conn, "user", "workspace.update", ws_id)
    return get_workspace(ws_id, conn)


@router.delete("/workspaces/{ws_id}")
def delete_workspace(ws_id: str, conn: sqlite3.Connection = Depends(get_db)):
    cur = conn.execute("DELETE FROM workspaces WHERE id=?", (ws_id,))
    if cur.rowcount == 0:
        raise HTTPException(404, "Workspace not found")
    audit(conn, "user", "workspace.delete", ws_id)
    return {"deleted": ws_id}
