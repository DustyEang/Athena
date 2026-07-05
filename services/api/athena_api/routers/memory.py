"""Memory CRUD + search endpoints."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..db import audit, get_db
from ..memory import CATEGORIES, MEMORY_MODES, MemoryStore

router = APIRouter(tags=["memory"])


class MemoryCreate(BaseModel):
    content: str = Field(min_length=1)
    category: str = "notes"
    workspace_id: str | None = None
    source: str = "user"
    importance: float = Field(default=0.5, ge=0, le=1)
    confidence: float = Field(default=0.8, ge=0, le=1)
    pending: bool = False   # proposals await approval before entering recall


class MemoryUpdate(BaseModel):
    content: str | None = None
    category: str | None = None
    importance: float | None = Field(default=None, ge=0, le=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    workspace_id: str | None = None


@router.get("/memory/categories")
def categories():
    return {"categories": CATEGORIES, "modes": MEMORY_MODES}


@router.get("/memory")
def list_memories(
    category: str | None = None, workspace_id: str | None = None,
    q: str | None = None, pending: bool = False,
    conn: sqlite3.Connection = Depends(get_db),
):
    store = MemoryStore(conn)
    if q:
        return store.search(q, limit=50)
    return store.list(category=category, workspace_id=workspace_id, pending=pending)


@router.post("/memory/{mem_id}/approve")
def approve_memory(mem_id: str, conn: sqlite3.Connection = Depends(get_db)):
    """Accept a proposed (pending) memory so it becomes recallable."""
    mem = MemoryStore(conn).approve(mem_id)
    if mem is None:
        raise HTTPException(404, "Memory not found")
    audit(conn, "user", "memory.approve", mem_id)
    return mem


@router.post("/memory")
def create_memory(body: MemoryCreate, conn: sqlite3.Connection = Depends(get_db)):
    store = MemoryStore(conn)
    mem = store.add(
        body.content, body.category, workspace_id=body.workspace_id,
        source=body.source, importance=body.importance, confidence=body.confidence,
        pending=body.pending,
    )
    audit(conn, "user", "memory.create", f"{body.category}: {body.content[:100]}")
    return mem


@router.patch("/memory/{mem_id}")
def update_memory(mem_id: str, body: MemoryUpdate, conn: sqlite3.Connection = Depends(get_db)):
    mem = MemoryStore(conn).update(mem_id, **body.model_dump(exclude_none=True))
    if mem is None:
        raise HTTPException(404, "Memory not found")
    audit(conn, "user", "memory.update", mem_id)
    return mem


@router.delete("/memory/{mem_id}")
def delete_memory(mem_id: str, conn: sqlite3.Connection = Depends(get_db)):
    if not MemoryStore(conn).delete(mem_id):
        raise HTTPException(404, "Memory not found")
    audit(conn, "user", "memory.delete", mem_id)
    return {"deleted": mem_id}
