"""Logging: rotating file logs + in-memory ring buffer served at /api/logs.

Every request gets a request_id (middleware in main.py). Providers, the
router, and the tool executor all log through the standard `logging` module,
so anything using `logging.getLogger("athena.*")` shows up in the debug UI.
"""
from __future__ import annotations

import collections
import logging
import time
from logging.handlers import RotatingFileHandler
from typing import Any

from .config import get_settings

RING_SIZE = 2000
_ring: collections.deque[dict[str, Any]] = collections.deque(maxlen=RING_SIZE)


class RingBufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        _ring.append(
            {
                "ts": time.time(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "request_id": getattr(record, "request_id", ""),
            }
        )


def get_ring_logs(level: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    logs = list(_ring)
    if level:
        order = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
        threshold = order.get(level.upper(), 10)
        logs = [l for l in logs if order.get(l["level"], 0) >= threshold]
    return logs[-limit:]


def setup_logging() -> None:
    root = logging.getLogger()
    if any(isinstance(h, RingBufferHandler) for h in root.handlers):
        return  # already configured (e.g. under test re-imports)
    root.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    file_handler = RotatingFileHandler(
        get_settings().resolved_data_dir / "logs" / "athena.log",
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)

    console = logging.StreamHandler()
    console.setFormatter(fmt)

    root.addHandler(file_handler)
    root.addHandler(console)
    root.addHandler(RingBufferHandler())
