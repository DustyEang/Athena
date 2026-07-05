import { useEffect } from "react";
import { api } from "./lib/api";
import { useAppStore, type View } from "./lib/store";
import ChatView from "./views/ChatView";
import HealthView from "./views/HealthView";
import LogsView from "./views/LogsView";
import MemoryView from "./views/MemoryView";
import PluginsView from "./views/PluginsView";
import SettingsView from "./views/SettingsView";
import WorkspacesView from "./views/WorkspacesView";

const NAV: { id: View; label: string; icon: string }[] = [
  { id: "chat", label: "Chat", icon: "◉" },
  { id: "memory", label: "Memory", icon: "◈" },
  { id: "workspaces", label: "Workspaces", icon: "▣" },
  { id: "plugins", label: "Plugins", icon: "✦" },
  { id: "health", label: "System", icon: "♥" },
  { id: "logs", label: "Logs", icon: "≡" },
  { id: "settings", label: "Settings", icon: "⚙" },
];

export default function App() {
  const { view, setView, backendUp, setBackendUp, workspaces, setWorkspaces,
    activeWorkspaceId, setActiveWorkspaceId } = useAppStore();

  useEffect(() => {
    let alive = true;
    const check = async () => {
      try {
        await api.healthFull();
        if (!alive) return;
        setBackendUp(true);
        if (useAppStore.getState().workspaces.length === 0) {
          const ws = await api.workspaces();
          if (alive) setWorkspaces(ws);
        }
      } catch {
        if (alive) setBackendUp(false);
      }
    };
    check();
    const t = setInterval(check, 10000);
    return () => { alive = false; clearInterval(t); };
  }, [setBackendUp, setWorkspaces]);

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <aside
        className="flex w-52 flex-col border-r px-3 py-4"
        style={{ borderColor: "var(--athena-border)", background: "var(--athena-panel)" }}
      >
        <div className="mb-6 flex items-center gap-3 px-2">
          <div className="orb orb-idle" style={{ width: 28, height: 28 }} />
          <span className="text-lg font-semibold tracking-[0.25em]">ATHENA</span>
        </div>

        <nav className="flex flex-col gap-1">
          {NAV.map((item) => (
            <button
              key={item.id}
              onClick={() => setView(item.id)}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition
                ${view === item.id ? "bg-sky-500/15 text-sky-300" : "hover:bg-white/5"}`}
              style={view === item.id ? {} : { color: "var(--athena-dim)" }}
            >
              <span className="w-4 text-center">{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>

        <div className="mt-auto space-y-3 px-2">
          <select
            value={activeWorkspaceId ?? ""}
            onChange={(e) => setActiveWorkspaceId(e.target.value || null)}
            className="w-full rounded-md border bg-transparent px-2 py-1.5 text-xs"
            style={{ borderColor: "var(--athena-border)", color: "var(--athena-text)" }}
            title="Active workspace"
          >
            <option value="" style={{ background: "var(--athena-panel)" }}>No workspace</option>
            {workspaces.map((w) => (
              <option key={w.id} value={w.id} style={{ background: "var(--athena-panel)" }}>
                {w.name}
              </option>
            ))}
          </select>
          <div className="flex items-center gap-2 text-xs" style={{ color: "var(--athena-dim)" }}>
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{
                background: backendUp === null ? "#eab308" : backendUp ? "#34d399" : "var(--athena-danger)",
              }}
            />
            {backendUp === null ? "connecting…" : backendUp ? "backend online" : "backend offline"}
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="min-w-0 flex-1 overflow-hidden">
        {backendUp === false && view !== "settings" ? (
          <div className="flex h-full flex-col items-center justify-center gap-4 p-8 text-center">
            <div className="orb orb-idle" style={{ width: 80, height: 80, opacity: 0.4 }} />
            <h2 className="text-xl font-medium">Backend not reachable</h2>
            <p className="max-w-md text-sm" style={{ color: "var(--athena-dim)" }}>
              Start it from the repo root with <code className="text-sky-300">scripts\dev-api.ps1</code>{" "}
              (or <code className="text-sky-300">uvicorn athena_api.main:app --port 8765</code> from{" "}
              <code>services/api</code>). This screen retries every 10 seconds.
            </p>
          </div>
        ) : (
          <>
            {view === "chat" && <ChatView />}
            {view === "memory" && <MemoryView />}
            {view === "workspaces" && <WorkspacesView />}
            {view === "plugins" && <PluginsView />}
            {view === "health" && <HealthView />}
            {view === "logs" && <LogsView />}
            {view === "settings" && <SettingsView />}
          </>
        )}
      </main>
    </div>
  );
}
