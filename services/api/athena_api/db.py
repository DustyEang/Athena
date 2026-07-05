"""SQLite persistence layer (stdlib sqlite3 — zero extra dependencies).

Design notes for future contributors (Cursor):
- One connection per request via `get_db()` dependency; WAL mode for concurrency.
- FTS5 virtual tables power memory + file search today. A `VectorStore`
  interface (memory/vector.py) exists so Chroma/Qdrant can replace FTS later
  without touching callers.
- Schema migrations: bump SCHEMA_VERSION and append idempotent DDL in
  `_migrate()`. Keep everything `CREATE ... IF NOT EXISTS` where possible.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from typing import Any, Iterator

from .config import get_settings

SCHEMA_VERSION = 2

# Idempotent-per-version migrations, applied in order above the stored version.
MIGRATIONS: dict[int, list[str]] = {
    2: [
        # Memory proposals: pending=1 rows await user approval (ask mode)
        "ALTER TABLE memories ADD COLUMN pending INTEGER NOT NULL DEFAULT 0",
        # Embedding vectors for semantic recall (memory/vector.py)
        """CREATE TABLE IF NOT EXISTS embeddings (
            id TEXT PRIMARY KEY,          -- matches memories.id (kind='memory')
            kind TEXT NOT NULL,
            dim INTEGER NOT NULL,
            vector BLOB NOT NULL,
            updated_at REAL NOT NULL
        )""",
    ],
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY, value TEXT
);

-- User-editable app settings (UI-changeable; env vars are process-level only)
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL              -- JSON-encoded
);

CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    root_path TEXT DEFAULT '',       -- optional folder this workspace maps to
    goals TEXT DEFAULT '',           -- current goals, freeform markdown
    roadmap TEXT DEFAULT '',         -- freeform markdown
    notes TEXT DEFAULT '',
    model_prefs TEXT DEFAULT '{}',   -- JSON: {"default_model": ..., "mode": ...}
    tool_settings TEXT DEFAULT '{}', -- JSON per-workspace tool overrides
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    workspace_id TEXT REFERENCES workspaces(id),
    title TEXT DEFAULT 'New conversation',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL,              -- user | assistant | system | tool
    content TEXT NOT NULL,
    provider TEXT DEFAULT '',
    model TEXT DEFAULT '',
    request_id TEXT DEFAULT '',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    workspace_id TEXT,               -- NULL = global user memory
    category TEXT NOT NULL,          -- see memory/store.py CATEGORIES
    content TEXT NOT NULL,
    source TEXT DEFAULT 'user',      -- user | chat | tool | import
    importance REAL DEFAULT 0.5,     -- 0..1
    confidence REAL DEFAULT 0.8,     -- 0..1
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content, category UNINDEXED, memory_id UNINDEXED
);

CREATE TABLE IF NOT EXISTS usage (
    id TEXT PRIMARY KEY,
    request_id TEXT,
    provider TEXT, model TEXT,
    task_type TEXT DEFAULT 'chat',
    tokens_in INTEGER DEFAULT 0,
    tokens_out INTEGER DEFAULT 0,
    est_cost_usd REAL DEFAULT 0,
    routing_reason TEXT DEFAULT '',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS tool_runs (
    id TEXT PRIMARY KEY,
    plugin TEXT NOT NULL,
    tool TEXT NOT NULL,
    args TEXT DEFAULT '{}',          -- JSON
    permission TEXT NOT NULL,
    status TEXT NOT NULL,            -- pending_confirmation | running | ok | error | denied
    result TEXT,                     -- JSON
    error TEXT,
    created_at REAL NOT NULL,
    resolved_at REAL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    actor TEXT NOT NULL,             -- user | athena | plugin:<name>
    action TEXT NOT NULL,
    detail TEXT DEFAULT '',
    created_at REAL NOT NULL
);

-- Folders the user has explicitly granted Athena read access to
CREATE TABLE IF NOT EXISTS folder_grants (
    id TEXT PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    granted_at REAL NOT NULL
);

-- Chunked file index for search/summarize (FTS today, vectors later)
CREATE TABLE IF NOT EXISTS file_chunks (
    id TEXT PRIMARY KEY,
    grant_id TEXT NOT NULL REFERENCES folder_grants(id),
    file_path TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    indexed_at REAL NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS file_chunks_fts USING fts5(
    content, file_path UNINDEXED, chunk_id UNINDEXED
);

CREATE TABLE IF NOT EXISTS plugin_state (
    name TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 1,
    settings TEXT DEFAULT '{}'       -- JSON, overrides manifest defaults
);
"""


def now() -> float:
    return time.time()


def new_id() -> str:
    return uuid.uuid4().hex[:16]


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(get_settings().db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)  # v1 base shape; migrations bring it current
        row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        version = int(row["value"]) if row else 1
        if row is None:
            conn.execute("INSERT INTO meta(key,value) VALUES('schema_version','1')")
        for target in sorted(MIGRATIONS):
            if target <= version:
                continue
            for statement in MIGRATIONS[target]:
                try:
                    conn.execute(statement)
                except sqlite3.OperationalError as exc:
                    # e.g. duplicate column when a migration partially applied
                    if "duplicate column" not in str(exc).lower():
                        raise
            version = target
        conn.execute("UPDATE meta SET value=? WHERE key='schema_version'", (str(version),))
        _seed_workspaces(conn)
        conn.commit()
    finally:
        conn.close()


def _seed_workspaces(conn: sqlite3.Connection) -> None:
    """Seed the user's known project workspaces on first run."""
    if conn.execute("SELECT COUNT(*) c FROM workspaces").fetchone()["c"] > 0:
        return
    seeds = [
        ("Athena", "Athena itself — this assistant platform."),
        ("Flow", "Internal operations / project management platform."),
        ("QA Agent", "Document review vs SOPs, manufacturer charts, quality rules."),
        ("Business Ops", "Tasks, bugs, SOPs, scheduling, strategy, automation."),
        ("AI Server", "Future hosted Athena brain: inference, remote access, jobs."),
        ("General Notes", "Everything that doesn't fit a project yet."),
    ]
    for name, desc in seeds:
        conn.execute(
            "INSERT INTO workspaces(id,name,description,created_at) VALUES(?,?,?,?)",
            (new_id(), name, desc, now()),
        )


@contextmanager
def db_conn() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_db() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency."""
    with db_conn() as conn:
        yield conn


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


def audit(conn: sqlite3.Connection, actor: str, action: str, detail: str = "") -> None:
    conn.execute(
        "INSERT INTO audit_log(id,actor,action,detail,created_at) VALUES(?,?,?,?,?)",
        (new_id(), actor, action, detail, now()),
    )


def get_setting(conn: sqlite3.Connection, key: str, default: Any = None) -> Any:
    row = conn.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute(
        "INSERT INTO app_settings(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, json.dumps(value)),
    )
