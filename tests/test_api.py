"""Smoke tests — prove the foundation boots and the core loops work.

Run from repo root (venv active):  pytest tests -q
Uses a temp data dir so it never touches your real Athena database.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "services" / "api"))

_tmp = tempfile.mkdtemp(prefix="athena-test-")
os.environ["ATHENA_DATA_DIR"] = _tmp
os.environ["ATHENA_FABLE5_API_KEY"] = ""       # force degraded mode
os.environ["ATHENA_OLLAMA_URL"] = "http://localhost:1"  # unreachable on purpose

from fastapi.testclient import TestClient  # noqa: E402

from athena_api.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_full_degraded(client):
    r = client.get("/api/health/full")
    assert r.status_code == 200
    body = r.json()
    assert body["database"]["ok"] is True
    providers = {p["name"]: p for p in body["providers"]}
    assert providers["mock"]["available"] is True
    assert providers["ollama"]["available"] is False   # degraded, not broken
    assert providers["fable5"]["available"] is False


def test_chat_streams_via_mock(client):
    with client.stream("POST", "/api/chat", json={"message": "hello athena"}) as r:
        assert r.status_code == 200
        events = []
        for line in r.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    types = [e["type"] for e in events]
    assert types[0] == "routing"
    assert events[0]["provider"] == "mock"   # no ollama, no key → mock
    assert "delta" in types
    assert types[-1] == "done"


def test_memory_crud_and_search(client):
    r = client.post("/api/memory", json={
        "content": "User prefers dark mode and local models",
        "category": "user_preferences", "importance": 0.9,
    })
    assert r.status_code == 200
    mem_id = r.json()["id"]

    r = client.get("/api/memory", params={"q": "dark mode"})
    assert any(m["id"] == mem_id for m in r.json())

    r = client.patch(f"/api/memory/{mem_id}", json={"importance": 1.0})
    assert r.json()["importance"] == 1.0

    assert client.delete(f"/api/memory/{mem_id}").status_code == 200


def test_workspaces_seeded_and_crud(client):
    names = [w["name"] for w in client.get("/api/workspaces").json()]
    assert {"Athena", "Flow", "QA Agent"}.issubset(set(names))

    r = client.post("/api/workspaces", json={"name": "Test WS"})
    ws_id = r.json()["id"]
    r = client.patch(f"/api/workspaces/{ws_id}", json={"goals": "ship v1"})
    assert r.json()["goals"] == "ship v1"
    assert client.delete(f"/api/workspaces/{ws_id}").status_code == 200


def test_settings_roundtrip(client):
    r = client.put("/api/settings", json={"values": {"task_mode": "cheap", "bogus_key": 1}})
    assert r.json()["applied"] == {"task_mode": "cheap"}
    settings = client.get("/api/settings").json()
    assert settings["task_mode"] == "cheap"
    assert settings["_env"]["fable5_configured"] is False


def test_plugin_registry_and_echo_tool(client):
    plugins = {p["name"]: p for p in client.get("/api/plugins").json()}
    assert "core" in plugins and "files" in plugins and "flow" in plugins
    assert plugins["flow"]["placeholder"] is True

    r = client.post("/api/tools/execute", json={
        "plugin": "core", "tool": "echo", "args": {"text": "ping"},
    })
    assert r.json()["status"] == "ok"
    assert r.json()["result"]["echo"] == "ping"


def test_sensitive_tool_requires_confirmation(client):
    r = client.post("/api/tools/execute", json={
        "plugin": "core", "tool": "launch_app", "args": {"app": "notepad"},
    })
    run = r.json()
    assert run["status"] == "pending_confirmation"
    # Deny it — nothing should launch during tests.
    r = client.post(f"/api/tools/confirm/{run['id']}", json={"approved": False})
    assert r.json()["status"] == "denied"


def test_placeholder_plugin_is_honest(client):
    r = client.post("/api/tools/execute", json={
        "plugin": "flow", "tool": "list_projects", "args": {},
    })
    assert r.json()["status"] == "error"
    assert "placeholder" in r.json()["error"].lower()


def test_file_grant_required(client):
    r = client.post("/api/files/read", json={"path": "C:/Windows/win.ini"})
    assert r.status_code == 403


def test_routing_preview_explains(client):
    r = client.post("/api/models/route-preview", json={"message": "hi"})
    body = r.json()
    assert body["tier"] in ("local", "mock")
    assert body["reason"]


# ---------- Tier 1: agent tool loop ----------

def _chat_events(client, message):
    with client.stream("POST", "/api/chat", json={"message": message}) as r:
        assert r.status_code == 200
        return [json.loads(l[6:]) for l in r.iter_lines() if l.startswith("data: ")]


def test_agent_loop_runs_read_only_tool(client):
    events = _chat_events(client, 'please !tool core.echo {"text": "agent-ping"}')
    types = [e["type"] for e in events]
    assert events[0]["type"] == "routing" and events[0]["agent_mode"] is True
    assert "tool_call" in types and "tool_result" in types
    call = next(e for e in events if e["type"] == "tool_call")
    assert (call["plugin"], call["tool"]) == ("core", "echo")
    result = next(e for e in events if e["type"] == "tool_result")
    assert result["status"] == "ok" and "agent-ping" in result["preview"]
    assert types[-1] == "done"


def test_agent_loop_respects_confirmation_gate(client):
    events = _chat_events(client, '!tool core.launch_app {"app": "notepad"}')
    result = next(e for e in events if e["type"] == "tool_result")
    assert result["status"] == "pending_confirmation"  # NOT executed
    # The pending run is visible in the activity feed; deny it to clean up.
    pending = client.get("/api/tools/runs?status=pending_confirmation").json()
    assert pending
    client.post(f"/api/tools/confirm/{pending[0]['id']}", json={"approved": False})


def test_agent_loop_rejects_unknown_tool(client):
    events = _chat_events(client, '!tool gmail.send_email {}')
    # gmail is a placeholder: not offered to the model, so no tool_call happens
    assert not any(e["type"] == "tool_call" for e in events)
    assert any(e["type"] == "done" for e in events)


# ---------- Tier 1: memory proposals ----------

def test_memory_proposal_approve_flow(client):
    r = client.post("/api/memory", json={
        "content": "User's favorite test framework is pytest",
        "category": "user_preferences", "pending": True, "source": "chat",
    })
    mem_id = r.json()["id"]
    assert r.json()["pending"] == 1

    # Pending proposals are invisible to normal list and search
    assert all(m["id"] != mem_id for m in client.get("/api/memory").json())
    assert all(m["id"] != mem_id
               for m in client.get("/api/memory", params={"q": "pytest"}).json())
    # ...but visible in the proposals view
    assert any(m["id"] == mem_id
               for m in client.get("/api/memory", params={"pending": "true"}).json())

    # Approve → becomes recallable
    r = client.post(f"/api/memory/{mem_id}/approve")
    assert r.json()["pending"] == 0
    assert any(m["id"] == mem_id
               for m in client.get("/api/memory", params={"q": "pytest"}).json())
    client.delete(f"/api/memory/{mem_id}")
