# Developer Mode

State: **read-only introspection implemented; change-making stubbed with a
strict contract.**

## Implemented now (developer plugin, all read_only)

- `git_status`, `git_diff` — via git CLI on granted folders
- `repo_tree` — file tree (skips node_modules etc)
- `code_search` — substring search across code files
- `run_command` — exists but ships **disabled**; if enabled it becomes
  `system_sensitive` (confirmation on every run)

Endpoints: `/api/developer/git-status|git-diff|repo-tree|plan-change`.

## The change-making contract (implement in this shape, no other)

```
1 scan      repo_tree + code_search + read_file (all read-only)
2 plan      model produces a ChangePlan: [{file, action, rationale, diff}]
3 review    UI renders diffs; nothing has touched disk yet (dry run default)
4 approve   user approves per-file or whole plan   ← hard gate
5 checkpoint git commit (or copy) BEFORE applying   ← rollback point
6 apply     write via files.write_file (confirmation-gated anyway)
7 verify    run tests (test runner tool, confirmation-gated)
8 changelog append entry: what changed, why, how to roll back
```

Non-negotiable rules (from the product owner):
- Never edit files silently — show planned changes first
- Ask approval before edits; support dry-run and review-before-apply
- Always generate a changelog; always be able to explain what changed
- Checkpoint before apply so rollback is one command

## Suggested next steps

- `ChangePlan` pydantic model + `/developer/plan-change` real implementation
  (route planning to Fable 5 — this is exactly the "hard, high-value" tier)
- Changelog table in SQLite + `docs/CHANGELOG-athena.md` mirror
- Test runner tool in the developer plugin (`pytest`, `npm run build`)
