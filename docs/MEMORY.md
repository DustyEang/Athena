# Memory

Files: `services/api/athena_api/memory/`.

## Model

Each memory: `content, category, workspace_id (null = global), source
(user|chat|tool|import), importance 0–1, confidence 0–1, timestamps`.

Categories: `user_preferences · active_projects · business_context ·
software_projects · personal_workflows · app_settings · model_preferences ·
tool_usage · frequent_commands · roadmaps · notes`

## Modes (Settings → Memory)

| Mode | Behavior |
|---|---|
| `off` | store nothing, recall nothing |
| `ask` *(default)* | Athena proposes; user approves each save |
| `auto_important` | auto-save facts that look important |
| `project_only` | only save with an active workspace, scoped to it |
| `full` | full assistant memory |

Athena never silently stores everything forever — that's a design rule, not
a setting.

## Recall

Chat injects `MemoryStore.recall_block(prompt)`: top-5 FTS5 hits, hard
character cap (~1.2k), formatted as a compact system block. Summarized
injection instead of dumping memory keeps premium token spend down.

## UI

Memory screen: search, category filter, add ("teach Athena"), importance
slider, delete (forget). Source and confidence are displayed on every entry.

## v1 gap → next steps

- **Extraction**: nothing auto-writes memory from chat yet. Implement a
  post-response step: local model extracts candidate facts → `ask` mode shows
  them as proposals in the UI → user approves. (Executor + memory API are
  ready; this is prompt + one endpoint + one UI card.)
- **Vector recall**: swap FTS for embeddings via `memory/vector.py` when
  semantic recall matters. Keep FTS as the degraded-mode fallback.
