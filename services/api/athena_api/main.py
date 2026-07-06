"""Athena API entrypoint.

Run:  uvicorn athena_api.main:app --port 8765 --reload
      (from services/api, with the venv active)
"""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .db import init_db
from .logging_setup import setup_logging
from .plugins import get_plugin_registry
from .routers import (
    chat, developer, files, health, logs, memory, models,
    plugins as plugins_router, settings as settings_router, tools, voice, workspaces,
)

log = logging.getLogger("athena.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    init_db()
    registry = get_plugin_registry()
    log.info("Athena API v%s up — %d plugins loaded", __version__, len(registry.plugins))
    yield
    log.info("Athena API shutting down")


app = FastAPI(title="Athena API", version=__version__, lifespan=lifespan)

# Desktop app origins: Vite dev server + Tauri webview + phones/tablets on
# the private network (RFC1918 ranges only — never public origins).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["tauri://localhost", "http://tauri.localhost"],
    allow_origin_regex=(
        r"http://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}"
        r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
        r"|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(:\d+)?"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request.state.request_id = uuid.uuid4().hex[:12]
    response = await call_next(request)
    response.headers["x-request-id"] = request.state.request_id
    return response


for router in (
    chat.router, models.router, memory.router, settings_router.router,
    tools.router, plugins_router.router, voice.router, health.router,
    logs.router, workspaces.router, files.router, developer.router,
):
    app.include_router(router, prefix="/api")


@app.get("/")
def root():
    return {"name": "Athena API", "version": __version__, "docs": "/docs"}
