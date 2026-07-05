"""Developer mode endpoints.

Read-only repo introspection is live (delegated to the developer plugin's
tools through the same permission-checked executor). Change-making features
are stubbed with a clear contract:

Planned flow (docs/DEVELOPER_MODE.md):
  scan → plan (model proposes changes) → show diff → user approves →
  apply patch → run tests → changelog entry → checkpoint (git commit)
Athena NEVER edits files silently; dry-run and review-before-apply are
mandatory parts of the design, not options.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..db import get_db
from ..plugins import execute_tool

router = APIRouter(tags=["developer"])


class RepoRequest(BaseModel):
    path: str


@router.post("/developer/git-status")
def git_status(body: RepoRequest, conn: sqlite3.Connection = Depends(get_db)):
    return execute_tool(conn, "developer", "git_status", {"path": body.path})


@router.post("/developer/git-diff")
def git_diff(body: RepoRequest, conn: sqlite3.Connection = Depends(get_db)):
    return execute_tool(conn, "developer", "git_diff", {"path": body.path})


@router.post("/developer/repo-tree")
def repo_tree(body: RepoRequest, conn: sqlite3.Connection = Depends(get_db)):
    return execute_tool(conn, "developer", "repo_tree", {"path": body.path})


@router.post("/developer/plan-change")
def plan_change() -> dict[str, Any]:
    """STUB — future: model-generated change plan with per-file diffs,
    approval workflow, apply + rollback checkpoint."""
    return {
        "status": "not_implemented",
        "design": "scan → plan → diff review → user approval → apply → test → changelog",
        "see": "docs/DEVELOPER_MODE.md",
    }
