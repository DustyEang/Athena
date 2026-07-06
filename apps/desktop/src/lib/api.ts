/** API client for the Athena backend. One place for base URL + SSE parsing. */
import type {
  ChatEvent, LogEntry, Memory, ModelOption, Plugin, ProviderStatus,
  ToolRun, Workspace,
} from "@shared/types";

// Follow the page's host so the app works from localhost AND from phones
// on the same network (the backend listens on 0.0.0.0:8765).
export const API_BASE = `http://${window.location.hostname || "127.0.0.1"}:8765/api`;

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${body.slice(0, 300)}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  // health / debug
  healthFull: () => http<Record<string, any>>("/health/full"),
  logs: (level?: string) =>
    http<LogEntry[]>(`/logs?limit=300${level ? `&level=${level}` : ""}`),

  // models
  providers: () => http<ProviderStatus[]>("/models/providers"),
  models: () => http<ModelOption[]>("/models"),
  usage: () => http<{ month_spend_usd: number; history: any[] }>("/models/usage"),

  // settings
  getSettings: () => http<Record<string, any>>("/settings"),
  putSettings: (values: Record<string, any>) =>
    http<{ applied: Record<string, any> }>("/settings", {
      method: "PUT", body: JSON.stringify({ values }),
    }),

  // memory
  listMemory: (params: { category?: string; workspace_id?: string; q?: string; pending?: string } = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v) as [string, string][],
    );
    return http<Memory[]>(`/memory?${qs}`);
  },
  approveMemory: (id: string) =>
    http<Memory>(`/memory/${id}/approve`, { method: "POST" }),
  memoryCategories: () => http<{ categories: string[]; modes: string[] }>("/memory/categories"),
  createMemory: (body: Partial<Memory> & { content: string }) =>
    http<Memory>("/memory", { method: "POST", body: JSON.stringify(body) }),
  updateMemory: (id: string, body: Partial<Memory>) =>
    http<Memory>(`/memory/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteMemory: (id: string) => http<{ deleted: string }>(`/memory/${id}`, { method: "DELETE" }),

  // workspaces
  workspaces: () => http<Workspace[]>("/workspaces"),
  createWorkspace: (body: { name: string; description?: string }) =>
    http<Workspace>("/workspaces", { method: "POST", body: JSON.stringify(body) }),
  updateWorkspace: (id: string, body: Partial<Workspace>) =>
    http<Workspace>(`/workspaces/${id}`, { method: "PATCH", body: JSON.stringify(body) }),

  // plugins / tools
  plugins: () => http<Plugin[]>("/plugins"),
  setPluginEnabled: (name: string, enabled: boolean) =>
    http(`/plugins/${name}/enabled`, { method: "POST", body: JSON.stringify({ enabled }) }),
  toolRuns: (status?: string) =>
    http<ToolRun[]>(`/tools/runs?limit=30${status ? `&status=${status}` : ""}`),
  executeTool: (plugin: string, tool: string, args: Record<string, unknown>) =>
    http<ToolRun>("/tools/execute", {
      method: "POST", body: JSON.stringify({ plugin, tool, args }),
    }),
  confirmTool: (runId: string, approved: boolean) =>
    http<ToolRun>(`/tools/confirm/${runId}`, {
      method: "POST", body: JSON.stringify({ approved }),
    }),

  // voice
  voiceStatus: () => http<Record<string, any>>("/voice/status"),
};

/** Text-to-speech: returns a playable WAV blob of Athena saying the text. */
export async function speakText(text: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}/voice/speak`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Speech failed (${res.status}): ${body.slice(0, 200)}`);
  }
  return res.blob();
}

/** Push-to-talk: send recorded audio, get the transcript back. */
export async function transcribeAudio(blob: Blob): Promise<string> {
  const form = new FormData();
  form.append("audio", blob, "recording.webm");
  const res = await fetch(`${API_BASE}/voice/transcribe`, { method: "POST", body: form });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Transcription failed (${res.status}): ${body.slice(0, 200)}`);
  }
  const data = (await res.json()) as { text: string };
  return data.text;
}

/** Stream a chat message; invokes onEvent for every SSE event. */
export async function streamChat(
  body: {
    message: string;
    conversation_id?: string | null;
    workspace_id?: string | null;
    model_override?: string | null;
    confirm_premium?: boolean;
  },
  onEvent: (e: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) throw new Error(`Chat failed: ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const line = part.trim();
      if (line.startsWith("data: ")) {
        try {
          onEvent(JSON.parse(line.slice(6)) as ChatEvent);
        } catch {
          /* ignore malformed frame */
        }
      }
    }
  }
}
