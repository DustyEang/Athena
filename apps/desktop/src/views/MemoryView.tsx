/** Memory inspector: browse, search, add, edit importance, delete. */
import { useCallback, useEffect, useState } from "react";
import type { Memory } from "@shared/types";
import { api } from "../lib/api";
import { useAppStore } from "../lib/store";

export default function MemoryView() {
  const { activeWorkspaceId } = useAppStore();
  const [memories, setMemories] = useState<Memory[]>([]);
  const [proposals, setProposals] = useState<Memory[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [filter, setFilter] = useState("");
  const [query, setQuery] = useState("");
  const [newContent, setNewContent] = useState("");
  const [newCategory, setNewCategory] = useState("notes");
  const [error, setError] = useState("");

  const refresh = useCallback(() => {
    api
      .listMemory({
        category: filter || undefined,
        q: query || undefined,
        workspace_id: activeWorkspaceId ?? undefined,
      })
      .then(setMemories)
      .catch((e) => setError(String(e)));
    api.listMemory({ pending: "true" }).then(setProposals).catch(() => {});
  }, [filter, query, activeWorkspaceId]);

  useEffect(() => {
    api.memoryCategories().then((c) => setCategories(c.categories)).catch(() => {});
  }, []);
  useEffect(refresh, [refresh]);

  return (
    <div className="flex h-full flex-col gap-4 p-6">
      <header className="flex flex-wrap items-center gap-3">
        <h2 className="text-lg font-semibold">Memory</h2>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search memory…"
          className="w-64 rounded-lg border bg-transparent px-3 py-2 text-sm"
          style={{ borderColor: "var(--athena-border)" }}
        />
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="rounded-lg border bg-transparent px-2 py-2 text-sm"
          style={{ borderColor: "var(--athena-border)" }}
        >
          <option value="" style={{ background: "var(--athena-panel)" }}>All categories</option>
          {categories.map((c) => (
            <option key={c} value={c} style={{ background: "var(--athena-panel)" }}>{c}</option>
          ))}
        </select>
      </header>

      {/* Add memory */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!newContent.trim()) return;
          api
            .createMemory({
              content: newContent,
              category: newCategory,
              workspace_id: activeWorkspaceId,
            })
            .then(() => { setNewContent(""); refresh(); })
            .catch((err) => setError(String(err)));
        }}
        className="flex gap-2"
      >
        <input
          value={newContent}
          onChange={(e) => setNewContent(e.target.value)}
          placeholder="Teach Athena something to remember…"
          className="flex-1 rounded-lg border bg-transparent px-3 py-2 text-sm"
          style={{ borderColor: "var(--athena-border)" }}
        />
        <select
          value={newCategory}
          onChange={(e) => setNewCategory(e.target.value)}
          className="rounded-lg border bg-transparent px-2 text-sm"
          style={{ borderColor: "var(--athena-border)" }}
        >
          {categories.map((c) => (
            <option key={c} value={c} style={{ background: "var(--athena-panel)" }}>{c}</option>
          ))}
        </select>
        <button
          className="rounded-lg px-4 text-sm font-medium"
          style={{ background: "var(--athena-core)", color: "#06121f" }}
        >
          Remember
        </button>
      </form>

      {error && <p className="text-xs" style={{ color: "var(--athena-danger)" }}>{error}</p>}

      {/* Proposed memories — Athena asks, you decide */}
      {proposals.length > 0 && (
        <div className="rounded-xl border p-3"
             style={{ borderColor: "var(--athena-core)", background: "rgba(56,189,248,0.06)" }}>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider"
             style={{ color: "var(--athena-core)" }}>
            Athena wants to remember ({proposals.length})
          </p>
          <div className="space-y-2">
            {proposals.map((p) => (
              <div key={p.id} className="flex items-center gap-3 text-sm">
                <span className="shrink-0 rounded-full border px-2 py-0.5 text-[10px]"
                      style={{ borderColor: "var(--athena-border)", color: "var(--athena-dim)" }}>
                  {p.category}
                </span>
                <span className="min-w-0 flex-1 truncate" title={p.content}>{p.content}</span>
                <button
                  onClick={() => api.approveMemory(p.id).then(refresh)}
                  className="shrink-0 rounded px-2.5 py-1 text-xs font-medium"
                  style={{ background: "var(--athena-core)", color: "#06121f" }}
                >
                  Remember
                </button>
                <button
                  onClick={() => api.deleteMemory(p.id).then(refresh)}
                  className="shrink-0 rounded border px-2.5 py-1 text-xs"
                  style={{ borderColor: "var(--athena-border)", color: "var(--athena-dim)" }}
                >
                  Forget
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex-1 space-y-2 overflow-y-auto">
        {memories.map((m) => (
          <div
            key={m.id}
            className="flex items-start gap-3 rounded-xl border p-3 text-sm"
            style={{ borderColor: "var(--athena-border)", background: "var(--athena-panel)" }}
          >
            <span
              className="mt-0.5 shrink-0 rounded-full border px-2 py-0.5 text-[10px]"
              style={{ borderColor: "var(--athena-border)", color: "var(--athena-dim)" }}
            >
              {m.category}
            </span>
            <div className="min-w-0 flex-1">
              <p className="whitespace-pre-wrap break-words">{m.content}</p>
              <p className="mt-1 text-[10px]" style={{ color: "var(--athena-dim)" }}>
                source: {m.source} · confidence {Math.round(m.confidence * 100)}% ·{" "}
                {new Date(m.updated_at * 1000).toLocaleString()}
              </p>
            </div>
            <label className="flex shrink-0 items-center gap-1 text-[10px]"
                   style={{ color: "var(--athena-dim)" }} title="Importance">
              ★
              <input
                type="range" min={0} max={1} step={0.1} defaultValue={m.importance}
                onMouseUp={(e) =>
                  api.updateMemory(m.id, { importance: Number((e.target as HTMLInputElement).value) })
                    .catch(() => {})}
                className="w-16 accent-sky-400"
              />
            </label>
            <button
              onClick={() => api.deleteMemory(m.id).then(refresh)}
              className="shrink-0 text-xs opacity-50 hover:opacity-100"
              title="Forget"
            >
              ✕
            </button>
          </div>
        ))}
        {memories.length === 0 && (
          <p className="text-sm" style={{ color: "var(--athena-dim)" }}>
            No memories yet. Athena's memory mode is "ask" by default — she proposes,
            you approve. You can also add facts manually above.
          </p>
        )}
      </div>
    </div>
  );
}
