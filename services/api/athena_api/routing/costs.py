"""Token/cost tracking. Prices are per-million-token USD estimates —
update PRICES when providers change pricing. Local models cost $0."""
from __future__ import annotations

import sqlite3
import time

from ..db import new_id

# (input $/Mtok, output $/Mtok)
PRICES: dict[str, tuple[float, float]] = {
    "claude-fable-5": (18.0, 90.0),   # placeholder — verify against real pricing
    "athena-mock": (0.0, 0.0),
    # OpenAI — estimates from the gpt-5 family price points; verify current
    "gpt-5.5": (1.25, 10.0),
    "gpt-5.4-mini": (0.25, 2.0),
    "gpt-5.4-nano": (0.05, 0.4),
    "gpt-4o-mini": (0.15, 0.6),
}
LOCAL_PROVIDERS = {"ollama", "mock", "athena-server"}


def estimate_cost(provider: str, model: str, tokens_in: int, tokens_out: int) -> float:
    if provider in LOCAL_PROVIDERS:
        return 0.0
    p_in, p_out = PRICES.get(model, (10.0, 40.0))  # unknown premium model: assume mid-tier
    return tokens_in / 1e6 * p_in + tokens_out / 1e6 * p_out


def record_usage(
    conn: sqlite3.Connection, *, request_id: str, provider: str, model: str,
    task_type: str, tokens_in: int, tokens_out: int, routing_reason: str,
) -> float:
    cost = estimate_cost(provider, model, tokens_in, tokens_out)
    conn.execute(
        "INSERT INTO usage(id,request_id,provider,model,task_type,tokens_in,"
        "tokens_out,est_cost_usd,routing_reason,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (new_id(), request_id, provider, model, task_type,
         tokens_in, tokens_out, cost, routing_reason, time.time()),
    )
    return cost


def month_spend(conn: sqlite3.Connection) -> float:
    """Premium spend since the 1st of the current month (UTC)."""
    now = time.gmtime()
    month_start = time.mktime((now.tm_year, now.tm_mon, 1, 0, 0, 0, 0, 0, 0))
    row = conn.execute(
        "SELECT COALESCE(SUM(est_cost_usd),0) c FROM usage WHERE created_at>=?",
        (month_start,),
    ).fetchone()
    return float(row["c"])
