"""File tools. All paths must live inside a user-granted folder
(folder_grants table) — enforced here for every tool, read or write."""
from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from athena_api.plugins.registry import ToolContext, ToolError


def _require_granted(ctx: ToolContext, raw_path: str) -> Path:
    p = Path(raw_path).resolve()
    for grant in ctx.conn.execute("SELECT path FROM folder_grants").fetchall():
        root = Path(grant["path"]).resolve()
        if p == root or root in p.parents:
            return p
    raise ToolError(
        f"'{raw_path}' is not inside a granted folder. "
        "Grant folder access first (Files → Grant folder)."
    )


def read_file(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    p = _require_granted(ctx, args["path"])
    if not p.is_file():
        raise ToolError(f"File not found: {p}")
    text = p.read_text(encoding="utf-8", errors="replace")
    return {"path": str(p), "content": text[:20000], "truncated": len(text) > 20000}


def search_folder(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    query = (args.get("query") or "").strip()
    if not query:
        raise ToolError("Search query is required")
    terms = " OR ".join(f'"{t}"' for t in query.replace('"', "").split())
    rows = ctx.conn.execute(
        "SELECT file_path, snippet(file_chunks_fts,0,'[',']','…',20) AS snippet "
        "FROM file_chunks_fts WHERE file_chunks_fts MATCH ? ORDER BY rank LIMIT 20",
        (terms,),
    ).fetchall()
    if not rows:
        return {"hits": [], "hint": "No results — has the folder been indexed yet?"}
    return {"hits": [dict(r) for r in rows]}


def summarize_document(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """Extractive v1: first paragraph + headings + length stats.
    TODO(cursor): route through the model router (local model first) for a
    real summary — see docs/MODEL_ROUTER.md for the tool→model pattern."""
    p = _require_granted(ctx, args["path"])
    if not p.is_file():
        raise ToolError(f"File not found: {p}")
    text = p.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    headings = [l.strip() for l in lines if l.strip().startswith("#")][:10]
    first_para = next((l.strip() for l in lines if l.strip() and not l.startswith("#")), "")
    return {
        "path": str(p),
        "summary": f"{first_para[:400]}",
        "headings": headings,
        "stats": {"lines": len(lines), "chars": len(text)},
        "note": "Extractive v1 summary — model-powered summarization is a Priority-2 TODO.",
    }


def compare_files(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    a = _require_granted(ctx, args["path_a"])
    b = _require_granted(ctx, args["path_b"])
    for p in (a, b):
        if not p.is_file():
            raise ToolError(f"File not found: {p}")
    diff = "\n".join(difflib.unified_diff(
        a.read_text(encoding="utf-8", errors="replace").splitlines(),
        b.read_text(encoding="utf-8", errors="replace").splitlines(),
        lineterm="", fromfile=str(a), tofile=str(b), n=2,
    ))
    return {"diff": diff[:30000] or "(files are identical)",
            "identical": not diff}


def write_file(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    # Only reachable AFTER user confirmation (user_confirmed_write).
    p = _require_granted(ctx, args["path"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(args.get("content", ""), encoding="utf-8")
    return {"written": str(p), "bytes": len(args.get("content", "").encode())}


def delete_file(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    # Only reachable AFTER user confirmation (user_confirmed_write).
    p = _require_granted(ctx, args["path"])
    if not p.is_file():
        raise ToolError(f"File not found: {p}")
    p.unlink()
    return {"deleted": str(p)}


def get_tools() -> dict[str, Any]:
    return {
        "read_file": read_file, "search_folder": search_folder,
        "summarize_document": summarize_document, "compare_files": compare_files,
        "write_file": write_file, "delete_file": delete_file,
    }
