"""Semantic recall — local embeddings + SQLite-backed vector store.

Design: embeddings come from Ollama (nomic-embed-text, ~274MB, fully local);
vectors live as float32 BLOBs in the `embeddings` table; similarity is
in-process cosine. At personal-assistant scale (thousands of memories) this
is faster than running a vector DB and has zero extra dependencies.

Degraded mode: if Ollama or the embed model is missing, everything returns
empty and MemoryStore silently falls back to FTS-only search. Availability
is re-checked at most once per minute.

Upgrade path: if the corpus ever outgrows in-process cosine (100k+ chunks),
put Chroma/Qdrant behind this same class — callers only use
embed_and_store / semantic_search / forget.
"""
from __future__ import annotations

import array
import logging
import math
import time
from dataclasses import dataclass

import httpx

from ..config import get_settings

log = logging.getLogger("athena.memory.vector")

_availability: tuple[float, bool] = (0.0, False)  # (checked_at, available)
_CHECK_TTL = 60.0


@dataclass
class VectorHit:
    id: str
    score: float


def embedder_available() -> bool:
    """Cheap cached check: is the embed model present in Ollama?"""
    global _availability
    checked_at, available = _availability
    if time.time() - checked_at < _CHECK_TTL:
        return available
    settings = get_settings()
    try:
        resp = httpx.get(f"{settings.ollama_url}/api/tags", timeout=2.0)
        resp.raise_for_status()
        names = [m["name"] for m in resp.json().get("models", [])]
        available = any(n.split(":")[0] == settings.embed_model.split(":")[0] for n in names)
    except Exception:  # noqa: BLE001 — availability check never raises
        available = False
    _availability = (time.time(), available)
    return available


def _embed(text: str) -> list[float] | None:
    settings = get_settings()
    try:
        resp = httpx.post(
            f"{settings.ollama_url}/api/embeddings",
            json={"model": settings.embed_model, "prompt": text[:4000]},
            timeout=15.0,
        )
        resp.raise_for_status()
        vec = resp.json().get("embedding")
        return vec if vec else None
    except Exception as exc:  # noqa: BLE001
        log.warning("Embedding failed: %s", exc)
        return None


def embed_and_store(conn, item_id: str, text: str, kind: str = "memory") -> bool:
    """Embed `text` and upsert its vector. Returns False when unavailable —
    callers must treat that as fine (FTS still covers the item)."""
    if not embedder_available():
        return False
    vec = _embed(text)
    if vec is None:
        return False
    blob = array.array("f", vec).tobytes()
    conn.execute(
        "INSERT INTO embeddings(id,kind,dim,vector,updated_at) VALUES(?,?,?,?,?) "
        "ON CONFLICT(id) DO UPDATE SET vector=excluded.vector, dim=excluded.dim, "
        "updated_at=excluded.updated_at",
        (item_id, kind, len(vec), blob, time.time()),
    )
    return True


def forget(conn, item_id: str) -> None:
    conn.execute("DELETE FROM embeddings WHERE id=?", (item_id,))


def semantic_search(conn, query: str, kind: str = "memory", top_k: int = 8) -> list[VectorHit]:
    """Cosine similarity over all stored vectors of `kind`."""
    if not embedder_available():
        return []
    q = _embed(query)
    if q is None:
        return []
    q_norm = math.sqrt(sum(x * x for x in q)) or 1.0

    hits: list[VectorHit] = []
    for row in conn.execute("SELECT id, vector FROM embeddings WHERE kind=?", (kind,)):
        v = array.array("f")
        v.frombytes(row["vector"])
        if len(v) != len(q):
            continue  # embed model changed dimensions; stale vector
        dot = sum(a * b for a, b in zip(q, v))
        v_norm = math.sqrt(sum(x * x for x in v)) or 1.0
        hits.append(VectorHit(id=row["id"], score=dot / (q_norm * v_norm)))
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:top_k]
