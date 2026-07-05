# Flow Integration

Flow is the internal operations/project-management platform. Athena ships a
**configured placeholder** — the contract is defined, nothing is hardcoded.

## Configuration (plugins/flow/manifest.json → settings)

| Setting | Purpose |
|---|---|
| `flow_url` | production Flow URL |
| `flow_local_dev_url` | local dev instance (default http://localhost:3000) |
| `api_key` | Flow API key (move to env once real: `ATHENA_FLOW_API_KEY`) |
| `default_project_id` | default project for captures |

## Declared tools (the contract to implement)

`open_flow · list_projects · create_task_idea · capture_bug · capture_idea ·
team_workload_summary · upcoming_work_queue · generate_roadmap ·
qa_review_queue`

All `network_access` → confirmation-gated once implemented (they can write
to a business system).

## Implementation plan

1. Decide the auth story on Flow's side (service account / API key — note:
   Flow currently uses Supabase; a dedicated API surface or RLS-safe service
   role will be needed).
2. Write `plugins/flow/handler.py` with an httpx client reading
   `ctx.plugin_settings`; flip `"placeholder": false`.
3. Start with the two highest-value tools: `capture_bug` and
   `create_task_idea` (Athena as the capture inbox for the team).
4. `generate_roadmap` routes through the model router (premium tier — it's
   exactly the "hard planning" case) using Flow data as context.
5. QA review queue plugs into the QA agent (QA_AGENT_ROADMAP.md) so Flow can
   show review results as a tab/module.

## UX intents (from the product owner)

AI idea bubble → `capture_idea`; bug capture → `capture_bug`; admin
dashboard insights → `team_workload_summary`; employee task queue support →
`upcoming_work_queue`.
