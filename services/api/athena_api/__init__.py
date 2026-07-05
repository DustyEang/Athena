"""Athena API — local-first AI assistant backend.

Package layout:
    config.py        env-driven settings (pydantic-settings)
    db.py            SQLite (stdlib) with FTS5 search, schema + helpers
    logging_setup.py file + in-memory ring-buffer logging
    providers/       model provider interface + implementations
    routing/         task classification + cost-aware model routing
    memory/          long-term memory store (categories, importance, FTS)
    plugins/         manifest-driven plugin registry + tool executor
    routers/         FastAPI route modules (one per domain)
"""

__version__ = "0.1.0"
