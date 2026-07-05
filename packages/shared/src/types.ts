/**
 * Shared API types — mirror of the FastAPI schemas in services/api.
 * Keep in sync when backend schemas change (single source of truth: backend
 * pydantic models; this file is the typed contract for all TS clients,
 * including the future web/mobile clients).
 */

export type ProviderKind = "local" | "premium" | "remote" | "mock";

export interface ProviderStatus {
  name: string;
  available: boolean;
  kind: ProviderKind;
  detail: string;
  models: string[];
}

export interface ModelOption {
  id: string; // "provider:model"
  provider: string;
  model: string;
  kind: ProviderKind;
  available: boolean;
}

export interface RoutingEvent {
  type: "routing";
  provider: string;
  model: string;
  tier: string;
  task_type: string;
  reason: string;
  warnings: string[];
  conversation_id: string;
  request_id: string;
  agent_mode?: boolean;
}

export type ChatEvent =
  | RoutingEvent
  | { type: "premium_confirmation_required"; provider: string; model: string }
  | { type: "delta"; text: string }
  | { type: "tool_call"; call_id: string; plugin: string; tool: string; args: Record<string, unknown> }
  | { type: "tool_result"; call_id: string; status: string; preview: string }
  | { type: "done"; usage: Usage }
  | { type: "error"; message: string };

export interface ToolActivity {
  call_id: string;
  plugin: string;
  tool: string;
  status: string; // running → ok | error | denied | pending_confirmation
  preview?: string;
}

export interface Usage {
  tokens_in: number;
  tokens_out: number;
  est_cost_usd: number;
  provider: string;
  model: string;
}

export interface Memory {
  id: string;
  workspace_id: string | null;
  category: string;
  content: string;
  source: string;
  importance: number;
  confidence: number;
  created_at: number;
  updated_at: number;
  pending: number; // 1 = proposed, awaiting user approval
}

export interface Workspace {
  id: string;
  name: string;
  description: string;
  root_path: string;
  goals: string;
  roadmap: string;
  notes: string;
  model_prefs: Record<string, unknown>;
  tool_settings: Record<string, unknown>;
  created_at: number;
}

export interface PluginTool {
  name: string;
  description: string;
  permission: string;
  implemented: boolean;
}

export interface Plugin {
  name: string;
  display_name: string;
  description: string;
  version: string;
  permission: string;
  placeholder: boolean;
  enabled: boolean;
  load_error: string;
  settings: Record<string, unknown>;
  tools: PluginTool[];
}

export interface ToolRun {
  id: string;
  plugin: string;
  tool: string;
  args: Record<string, unknown>;
  permission: string;
  status: "pending_confirmation" | "running" | "ok" | "error" | "denied";
  result?: unknown;
  error?: string;
  created_at: number;
  resolved_at?: number;
}

export interface LogEntry {
  ts: number;
  level: string;
  logger: string;
  message: string;
  request_id: string;
}

export type OrbState = "idle" | "listening" | "thinking" | "speaking";
