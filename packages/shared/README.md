# @athena/shared

Shared TypeScript types for all Athena clients (desktop today; web/mobile
later). Imported by the desktop app via the `@shared/*` path alias — no build
step needed.

Rule: the backend pydantic models are the source of truth. When an API schema
changes, update `src/types.ts` in the same commit.
