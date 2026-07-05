"""Developer tools — read-only repo introspection.

`run_command` ships with permission "disabled" in the manifest. To enable it
later: change its permission to "system_sensitive" (still confirmation-gated)
— a deliberate two-step so risky power is opt-in, never default.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from athena_api.plugins.registry import ToolContext, ToolError

SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "target", ".vite"}
CODE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".rs", ".go", ".java",
             ".css", ".html", ".sql", ".ps1", ".sh", ".toml", ".yaml", ".yml"}


def _require_granted(ctx: ToolContext, raw_path: str) -> Path:
    p = Path(raw_path).resolve()
    for grant in ctx.conn.execute("SELECT path FROM folder_grants").fetchall():
        root = Path(grant["path"]).resolve()
        if p == root or root in p.parents:
            return p
    raise ToolError(f"'{raw_path}' is not inside a granted folder.")


def _git(cwd: Path, *cmd: str) -> str:
    try:
        result = subprocess.run(
            ["git", *cmd], cwd=cwd, capture_output=True, text=True, timeout=20,
        )
    except FileNotFoundError as exc:
        raise ToolError("git is not installed or not on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise ToolError("git command timed out") from exc
    if result.returncode != 0:
        raise ToolError(f"git failed: {result.stderr.strip()[:300]}")
    return result.stdout


def git_status(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    p = _require_granted(ctx, args["path"])
    return {"status": _git(p, "status", "--short", "--branch")[:20000]}


def git_diff(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    p = _require_granted(ctx, args["path"])
    return {"diff": _git(p, "diff", "--stat", "-p")[:30000]}


def repo_tree(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    root = _require_granted(ctx, args["path"])
    max_depth = int(args.get("max_depth", 4))
    lines: list[str] = []

    def walk(d: Path, depth: int) -> None:
        if depth > max_depth or len(lines) > 500:
            return
        try:
            entries = sorted(d.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
        except OSError:
            return
        for entry in entries:
            if entry.name in SKIP_DIRS or entry.name.startswith("."):
                continue
            lines.append("  " * depth + ("📁 " if entry.is_dir() else "") + entry.name)
            if entry.is_dir():
                walk(entry, depth + 1)

    walk(root, 0)
    return {"tree": "\n".join(lines), "truncated": len(lines) > 500}


def code_search(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    root = _require_granted(ctx, args["path"])
    query = (args.get("query") or "").strip()
    if not query:
        raise ToolError("Search query is required")
    matches: list[dict[str, Any]] = []
    for path in root.rglob("*"):
        if len(matches) >= 50:
            break
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file() or path.suffix.lower() not in CODE_EXTS:
            continue
        try:
            for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if query.lower() in line.lower():
                    matches.append({"file": str(path), "line": i, "text": line.strip()[:200]})
                    if len(matches) >= 50:
                        break
        except OSError:
            continue
    return {"matches": matches, "truncated": len(matches) >= 50}


def run_command(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    # Unreachable while manifest permission is "disabled". If enabled it is
    # system_sensitive → user confirms every invocation.
    p = _require_granted(ctx, args["path"])
    result = subprocess.run(  # noqa: S602 — explicit user-confirmed command
        args["command"], cwd=p, capture_output=True, text=True, timeout=120, shell=True,
    )
    return {"stdout": result.stdout[:20000], "stderr": result.stderr[:5000],
            "exit_code": result.returncode}


def get_tools() -> dict[str, Any]:
    return {"git_status": git_status, "git_diff": git_diff, "repo_tree": repo_tree,
            "code_search": code_search, "run_command": run_command}
