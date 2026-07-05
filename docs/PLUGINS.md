# Plugins

Files: `plugins/*` (the plugins) and `services/api/athena_api/plugins/`
(registry + executor).

## Contract

```
plugins/<name>/
  manifest.json    identity, tools, permissions, settings, placeholder flag
  handler.py       get_tools() -> dict[tool_name, handler]  (omit if placeholder)
```

Handler signature:

```python
def my_tool(args: dict, ctx: ToolContext) -> dict:   # JSON-safe return
    # ctx.conn (sqlite), ctx.plugin_settings, ctx.workspace_id
    # raise ToolError("user-facing message") for expected failures
```

## Permission levels

| Level | Behavior |
|---|---|
| `read_only` | runs immediately |
| `user_confirmed_write` | pending confirmation → user approves in UI |
| `system_sensitive` | confirmation required; use for launch/run/send actions |
| `network_access` | confirmation when it can spend money or move data out |
| `disabled` | never runs (e.g. developer.run_command ships disabled) |

Enforced centrally in `executor.py` — handlers never check permissions
themselves. Every run and every approve/deny lands in `tool_runs` +
`audit_log`.

## Current plugins

| Plugin | State | Tools |
|---|---|---|
| core | **implemented** | echo, add_note, list_notes, launch_app (allowlisted, confirmed) |
| files | **implemented** | read, search (FTS index), summarize (extractive v1), compare, write*, delete* |
| developer | **implemented** | git_status, git_diff, repo_tree, code_search, run_command (disabled) |
| voice | placeholder | pipeline lives in backend; tools activate with STT/TTS install |
| flow | placeholder | see FLOW_INTEGRATION.md |
| qa_agent | placeholder | see QA_AGENT_ROADMAP.md |
| web_search, gmail, calendar, smart_home, business, server_connector | placeholders | manifests define the intended contract |

\* = confirmation-gated. All file tools additionally require the path to be
inside a user-granted folder (`folder_grants`).

## Adding a plugin

1. Create `plugins/myplugin/manifest.json` (copy core's as a template).
2. Add `handler.py` with `get_tools()`.
3. `POST /api/plugins/reload` (or restart backend).
4. It appears on the Plugins screen with its permission badges.

Implementing a placeholder = write `handler.py` + set `"placeholder": false`.
