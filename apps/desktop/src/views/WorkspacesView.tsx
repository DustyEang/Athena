/** Workspaces: project cards + goal/roadmap editing. */
import { useEffect, useState } from "react";
import type { Workspace } from "@shared/types";
import { api } from "../lib/api";
import { useAppStore } from "../lib/store";

export default function WorkspacesView() {
  const { workspaces, setWorkspaces, activeWorkspaceId, setActiveWorkspaceId } = useAppStore();
  const [selected, setSelected] = useState<Workspace | null>(null);
  const [newName, setNewName] = useState("");
  const [draft, setDraft] = useState({ goals: "", roadmap: "", notes: "" });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.workspaces().then(setWorkspaces).catch(() => {});
  }, [setWorkspaces]);

  useEffect(() => {
    if (selected) {
      setDraft({ goals: selected.goals, roadmap: selected.roadmap, notes: selected.notes });
      setSaved(false);
    }
  }, [selected]);

  return (
    <div className="flex h-full">
      <div className="w-80 space-y-2 overflow-y-auto border-r p-4"
           style={{ borderColor: "var(--athena-border)" }}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!newName.trim()) return;
            api.createWorkspace({ name: newName }).then(() => {
              setNewName("");
              api.workspaces().then(setWorkspaces);
            }).catch((err) => alert(String(err)));
          }}
          className="mb-3 flex gap-2"
        >
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="New workspace…"
            className="flex-1 rounded-lg border bg-transparent px-3 py-2 text-sm"
            style={{ borderColor: "var(--athena-border)" }}
          />
          <button className="rounded-lg px-3 text-sm font-medium"
                  style={{ background: "var(--athena-core)", color: "#06121f" }}>+</button>
        </form>
        {workspaces.map((w) => (
          <button
            key={w.id}
            onClick={() => setSelected(w)}
            className={`w-full rounded-xl border p-3 text-left text-sm transition hover:border-sky-500/50
              ${selected?.id === w.id ? "border-sky-500/60" : ""}`}
            style={{
              borderColor: selected?.id === w.id ? undefined : "var(--athena-border)",
              background: "var(--athena-panel)",
            }}
          >
            <div className="flex items-center justify-between">
              <span className="font-medium">{w.name}</span>
              {activeWorkspaceId === w.id && (
                <span className="text-[10px] text-sky-300">active</span>
              )}
            </div>
            <p className="mt-1 text-xs" style={{ color: "var(--athena-dim)" }}>
              {w.description || "No description"}
            </p>
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {!selected ? (
          <p className="text-sm" style={{ color: "var(--athena-dim)" }}>
            Select a workspace. Each workspace scopes memory, model preferences,
            goals, and (soon) files and tools.
          </p>
        ) : (
          <div className="max-w-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">{selected.name}</h2>
              <button
                onClick={() => setActiveWorkspaceId(selected.id)}
                className="rounded-lg border px-3 py-1.5 text-xs"
                style={{ borderColor: "var(--athena-border)" }}
              >
                Set active
              </button>
            </div>
            {(["goals", "roadmap", "notes"] as const).map((field) => (
              <div key={field}>
                <label className="text-xs font-semibold uppercase tracking-wider"
                       style={{ color: "var(--athena-dim)" }}>
                  {field}
                </label>
                <textarea
                  value={draft[field]}
                  onChange={(e) => { setDraft({ ...draft, [field]: e.target.value }); setSaved(false); }}
                  rows={field === "notes" ? 6 : 4}
                  className="mt-1 w-full rounded-xl border bg-transparent p-3 text-sm"
                  style={{ borderColor: "var(--athena-border)" }}
                  placeholder={`${field} for ${selected.name}…`}
                />
              </div>
            ))}
            <button
              onClick={() =>
                api.updateWorkspace(selected.id, draft).then((w) => {
                  setSaved(true);
                  setWorkspaces(workspaces.map((x) => (x.id === w.id ? w : x)));
                })}
              className="rounded-lg px-4 py-2 text-sm font-medium"
              style={{ background: "var(--athena-core)", color: "#06121f" }}
            >
              {saved ? "Saved ✓" : "Save"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
