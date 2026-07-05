/** Debug logs from the backend ring buffer. */
import { useEffect, useState } from "react";
import type { LogEntry } from "@shared/types";
import { api } from "../lib/api";

const LEVEL_COLOR: Record<string, string> = {
  ERROR: "var(--athena-danger)", CRITICAL: "var(--athena-danger)",
  WARNING: "var(--athena-tool)", INFO: "var(--athena-text)", DEBUG: "var(--athena-dim)",
};

export default function LogsView() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [level, setLevel] = useState("");

  useEffect(() => {
    const load = () => api.logs(level || undefined).then(setLogs).catch(() => {});
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [level]);

  return (
    <div className="flex h-full flex-col p-6">
      <div className="mb-3 flex items-center gap-3">
        <h2 className="text-lg font-semibold">Logs</h2>
        <select value={level} onChange={(e) => setLevel(e.target.value)}
                className="rounded-lg border bg-transparent px-2 py-1.5 text-xs"
                style={{ borderColor: "var(--athena-border)" }}>
          {["", "INFO", "WARNING", "ERROR"].map((l) => (
            <option key={l} value={l} style={{ background: "var(--athena-panel)" }}>
              {l || "All levels"}
            </option>
          ))}
        </select>
        <span className="text-xs" style={{ color: "var(--athena-dim)" }}>
          auto-refreshes · file logs in data/logs/athena.log
        </span>
      </div>
      <div className="flex-1 overflow-y-auto rounded-xl border p-3 font-mono text-xs"
           style={{ borderColor: "var(--athena-border)", background: "var(--athena-panel)" }}>
        {[...logs].reverse().map((l, i) => (
          <div key={i} className="flex gap-3 py-0.5">
            <span className="shrink-0" style={{ color: "var(--athena-dim)" }}>
              {new Date(l.ts * 1000).toLocaleTimeString()}
            </span>
            <span className="w-16 shrink-0" style={{ color: LEVEL_COLOR[l.level] }}>{l.level}</span>
            <span className="w-40 shrink-0 truncate" style={{ color: "var(--athena-dim)" }}>
              {l.logger}
            </span>
            <span className="break-all">{l.message}</span>
          </div>
        ))}
        {logs.length === 0 && <p style={{ color: "var(--athena-dim)" }}>No log entries.</p>}
      </div>
    </div>
  );
}
