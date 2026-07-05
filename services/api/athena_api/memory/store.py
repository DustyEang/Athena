"""Long-term memory store.

Memory rules (user-controlled — see `memory_mode` setting):
  off            never store anything
  ask            proposals: extracted memories saved as pending=1; the user
                 approves/rejects them in the Memory screen (default)
  auto_important auto-save facts that look important
  project_only   only save when a workspace is active, scoped to it
  full           full assistant memory

Search is hybrid: SQLite FTS5 (keyword) fused with local-embedding cosine
similarity (memory/vector.py, nomic-embed-text via Ollama). When embeddings
are unavailable, FTS alone serves — degraded, never broken.
"""
from __future__ import annotations

import sqlite3
import time
from typing import Any

from ..db import new_id, rows_to_dicts
from . import vector

CATEGORIES = [
    "user_preferences", "active_projects", "business_context", "software_projects",
    "personal_workflows", "app_settings", "model_preferences", "tool_usage",
    "frequent_commands", "roadmaps", "notes",
]
MEMORY_MODES = ["off", "ask", "auto_important", "project_only", "full"]


class MemoryStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(
        self, content: str, category: str = "notes", *,
        workspace_id: str | None = None, source: str = "user",
        importance: float = 0.5, confidence: float = 0.8,
        pending: bool = False,
    ) -> dict[str, Any]:
        if category not in CATEGORIES:
            category = "notes"
        mem_id = new_id()
        ts = time.time()
        self.conn.execute(
            "INSERT INTO memories(id,workspace_id,category,content,source,"
            "importance,confidence,created_at,updated_at,pending) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (mem_id, workspace_id, category, content, source, importance,
             confidence, ts, ts, int(pending)),
        )
        # Pending proposals stay out of FTS/vector until approved — recall
        # must never surface facts the user hasn't accepted.
        if not pending:
            self._index(mem_id, content, category)
        return self.get(mem_id)

    def _index(self, mem_id: str, content: str, category: str) -> None:
        self.conn.execute(
            "INSERT INTO memories_fts(content,category,memory_id) VALUES(?,?,?)",
            (content, category, mem_id),
        )
        vector.embed_and_store(self.conn, mem_id, content, kind="memory")

    def get(self, mem_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM memories WHERE id=?", (mem_id,)).fetchone()
        return dict(row) if row else None

    def list(
        self, *, category: str | None = None, workspace_id: str | None = None,
        pending: bool | None = False, limit: int = 200,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM memories WHERE 1=1"
        params: list[Any] = []
        if pending is not None:
            query += " AND pending=?"
            params.append(int(pending))
        if category:
            query += " AND category=?"
            params.append(category)
        if workspace_id:
            query += " AND (workspace_id=? OR workspace_id IS NULL)"
            params.append(workspace_id)
        query += " ORDER BY importance DESC, updated_at DESC LIMIT ?"
        params.append(limit)
        return rows_to_dicts(self.conn.execute(query, params).fetchall())

    def approve(self, mem_id: str) -> dict[str, Any] | None:
        """Accept a pending proposal: flips pending off and indexes it."""
        mem = self.get(mem_id)
        if mem is None or not mem["pending"]:
            return mem
        self.conn.execute(
            "UPDATE memories SET pending=0, updated_at=? WHERE id=?",
            (time.time(), mem_id),
        )
        self._index(mem_id, mem["content"], mem["category"])
        return self.get(mem_id)

    def update(self, mem_id: str, **fields: Any) -> dict[str, Any] | None:
        allowed = {"content", "category", "importance", "confidence", "workspace_id"}
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not updates:
            return self.get(mem_id)
        sets = ", ".join(f"{k}=?" for k in updates)
        self.conn.execute(
            f"UPDATE memories SET {sets}, updated_at=? WHERE id=?",
            (*updates.values(), time.time(), mem_id),
        )
        if "content" in updates or "category" in updates:
            self.conn.execute("DELETE FROM memories_fts WHERE memory_id=?", (mem_id,))
            mem = self.get(mem_id)
            if mem and not mem["pending"]:
                self._index(mem_id, mem["content"], mem["category"])
        return self.get(mem_id)

    def delete(self, mem_id: str) -> bool:
        self.conn.execute("DELETE FROM memories_fts WHERE memory_id=?", (mem_id,))
        vector.forget(self.conn, mem_id)
        cur = self.conn.execute("DELETE FROM memories WHERE id=?", (mem_id,))
        return cur.rowcount > 0

    # ---------- search ----------

    def search(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        """Hybrid search: FTS5 + semantic cosine, fused by reciprocal rank.
        Pending proposals never appear (they're not indexed)."""
        fts_ids = self._fts_ids(query, limit=limit * 2)
        sem_ids = [h.id for h in vector.semantic_search(self.conn, query, top_k=limit * 2)]

        # Reciprocal Rank Fusion: robust way to merge rankings without
        # comparable scores. k=60 is the standard damping constant.
        scores: dict[str, float] = {}
        for rank_list in (fts_ids, sem_ids):
            for rank, mem_id in enumerate(rank_list):
                scores[mem_id] = scores.get(mem_id, 0.0) + 1.0 / (60 + rank)
        ordered = sorted(scores, key=lambda i: scores[i], reverse=True)[:limit]

        out = []
        for mem_id in ordered:
            mem = self.get(mem_id)
            if mem and not mem["pending"]:
                out.append(mem)
        return out

    def _fts_ids(self, query: str, *, limit: int) -> list[str]:
        try:
            rows = self.conn.execute(
                "SELECT memory_id FROM memories_fts WHERE memories_fts MATCH ? "
                "ORDER BY rank LIMIT ?",
                (self._fts_escape(query), limit),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = self.conn.execute(
                "SELECT id AS memory_id FROM memories WHERE content LIKE ? AND pending=0 "
                "ORDER BY importance DESC LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
        return [r["memory_id"] for r in rows]

    def recall_block(self, query: str, *, limit: int = 5, max_chars: int = 1200) -> str:
        """Compact context block for prompt injection — summarized recall,
        never a full memory dump (cost control)."""
        hits = self.search(query, limit=limit)
        if not hits:
            return ""
        lines, used = [], 0
        for h in hits:
            line = f"- [{h['category']}] {h['content'][:200]}"
            if used + len(line) > max_chars:
                break
            lines.append(line)
            used += len(line)
        return "Relevant things you remember about the user:\n" + "\n".join(lines)

    @staticmethod
    def _fts_escape(query: str) -> str:
        # Quote each term so user punctuation can't break FTS5 syntax
        terms = [t.replace('"', '""') for t in query.split() if t.strip()]
        return " OR ".join(f'"{t}"' for t in terms) if terms else '""'
