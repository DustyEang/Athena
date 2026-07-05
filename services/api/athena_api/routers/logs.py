"""Log endpoints — serve the in-memory ring buffer to the debug UI."""
from __future__ import annotations

from fastapi import APIRouter

from ..logging_setup import get_ring_logs

router = APIRouter(tags=["logs"])


@router.get("/logs")
def logs(level: str | None = None, limit: int = 200):
    return get_ring_logs(level=level, limit=min(limit, 1000))
