"""File & document system: folder grants, indexing, search, read.

Safety model (docs/SECURITY.md):
- Athena can only READ inside folders the user granted via POST /files/grants.
- Writes/deletes are NOT exposed here at all — they go through the plugin
  executor with user_confirmed_write permission (see plugins/files).
- Indexing chunks text files into SQLite FTS5. Embeddings/vector search is
  the upgrade path in memory/vector.py.

TODO(cursor): folder watching (watchdog), dropzone upload endpoint,
             per-file summaries cached in DB, "explain this repo" flow.
"""
from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db import audit, get_db, new_id, rows_to_dicts

log = logging.getLogger("athena.files")
router = APIRouter(tags=["files"])

TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".yaml", ".yml",
    ".toml", ".css", ".html", ".csv", ".sql", ".ps1", ".sh", ".rs", ".go", ".java",
}
CHUNK_CHARS = 1500
MAX_FILE_BYTES = 1_000_000
SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "target", ".vite"}


class GrantRequest(BaseModel):
    path: str


class ReadRequest(BaseModel):
    path: str
    max_chars: int = 20000


def _granted_root(conn: sqlite3.Connection, path: Path) -> sqlite3.Row | None:
    """Return the grant covering `path`, or None. Resolves symlinks/.. tricks."""
    resolved = path.resolve()
    for grant in conn.execute("SELECT * FROM folder_grants").fetchall():
        root = Path(grant["path"]).resolve()
        if resolved == root or root in resolved.parents:
            return grant
    return None


@router.get("/files/grants")
def list_grants(conn: sqlite3.Connection = Depends(get_db)):
    return rows_to_dicts(conn.execute("SELECT * FROM folder_grants ORDER BY path").fetchall())


@router.post("/files/grants")
def add_grant(body: GrantRequest, conn: sqlite3.Connection = Depends(get_db)):
    p = Path(body.path)
    if not p.exists() or not p.is_dir():
        raise HTTPException(400, f"Not an existing folder: {body.path}")
    grant_id = new_id()
    try:
        conn.execute(
            "INSERT INTO folder_grants(id,path,granted_at) VALUES(?,?,?)",
            (grant_id, str(p.resolve()), time.time()),
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(409, "Folder already granted") from exc
    audit(conn, "user", "files.grant", str(p))
    return {"id": grant_id, "path": str(p.resolve())}


@router.delete("/files/grants/{grant_id}")
def revoke_grant(grant_id: str, conn: sqlite3.Connection = Depends(get_db)):
    conn.execute("DELETE FROM file_chunks WHERE grant_id=?", (grant_id,))
    cur = conn.execute("DELETE FROM folder_grants WHERE id=?", (grant_id,))
    if cur.rowcount == 0:
        raise HTTPException(404, "Grant not found")
    audit(conn, "user", "files.revoke", grant_id)
    return {"revoked": grant_id}


@router.post("/files/grants/{grant_id}/index")
def index_folder(grant_id: str, conn: sqlite3.Connection = Depends(get_db)):
    """Walk the granted folder, chunk text files into FTS. Synchronous v1 —
    fine for project-sized folders; move to a background job for huge trees."""
    grant = conn.execute("SELECT * FROM folder_grants WHERE id=?", (grant_id,)).fetchone()
    if grant is None:
        raise HTTPException(404, "Grant not found")
    root = Path(grant["path"])

    conn.execute("DELETE FROM file_chunks WHERE grant_id=?", (grant_id,))
    conn.execute(
        "DELETE FROM file_chunks_fts WHERE chunk_id IN "
        "(SELECT id FROM file_chunks WHERE grant_id=?)", (grant_id,),
    )

    files_indexed = chunks = 0
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        files_indexed += 1
        for i in range(0, len(text), CHUNK_CHARS):
            chunk_id = new_id()
            content = text[i : i + CHUNK_CHARS]
            conn.execute(
                "INSERT INTO file_chunks(id,grant_id,file_path,chunk_index,content,indexed_at) "
                "VALUES(?,?,?,?,?,?)",
                (chunk_id, grant_id, str(path), i // CHUNK_CHARS, content, time.time()),
            )
            conn.execute(
                "INSERT INTO file_chunks_fts(content,file_path,chunk_id) VALUES(?,?,?)",
                (content, str(path), chunk_id),
            )
            chunks += 1
    audit(conn, "athena", "files.index", f"{root}: {files_indexed} files, {chunks} chunks")
    return {"files_indexed": files_indexed, "chunks": chunks}


@router.get("/files/search")
def search_files(q: str, limit: int = 20, conn: sqlite3.Connection = Depends(get_db)):
    terms = " OR ".join(f'"{t}"' for t in q.replace('"', "").split() if t)
    if not terms:
        return []
    try:
        rows = conn.execute(
            "SELECT file_path, snippet(file_chunks_fts, 0, '[', ']', '…', 20) AS snippet "
            "FROM file_chunks_fts WHERE file_chunks_fts MATCH ? ORDER BY rank LIMIT ?",
            (terms, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return rows_to_dicts(rows)


@router.post("/files/read")
def read_file(body: ReadRequest, conn: sqlite3.Connection = Depends(get_db)):
    p = Path(body.path)
    if _granted_root(conn, p) is None:
        raise HTTPException(403, "Path is not inside a granted folder. Grant access first.")
    if not p.is_file():
        raise HTTPException(404, "File not found")
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise HTTPException(400, f"Cannot read file: {exc}") from exc
    audit(conn, "athena", "files.read", str(p))
    return {"path": str(p), "truncated": len(text) > body.max_chars,
            "content": text[: body.max_chars]}
