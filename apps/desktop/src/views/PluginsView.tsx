/** Plugin registry: status, permissions, enable/disable, tool test-fire. */
import { useCallback, useEffect, useState } from "react";
import type { Plugin } from "@shared/types";
import { api } from "../lib/api";

const PERM_COLOR: Record<string, string> = {
  read_only: "#34d399",
  user_confirmed_write: "var(--athena-tool)",
  system_sensitive: "var(--athena-danger)",
  network_access: "var(--athena-premium)",
  disabled: "var(--athena-dim)",
};

export default function PluginsView() {
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [notice, setNotice] = useState("");

  const refresh = useCallback(() => {
    api.plugins().then(setPlugins).catch((e) => setNotice(String(e)));
  }, []);
  useEffect(refresh, [refresh]);

  return (
    <div className="h-full overflow-y-auto p-6">
      <h2 className="mb-1 text-lg font-semibold">Plugins</h2>
      <p className="mb-4 text-sm" style={{ color: "var(--athena-dim)" }}>
        Placeholders are architecture stubs — enabled UI, honest "not implemented"
        behavior. See docs/PLUGINS.md to implement one.
      </p>
      {notice && <p className="mb-3 text-xs" style={{ color: "var(--athena-tool)" }}>{notice}</p>}

      <div className="grid gap-4 xl:grid-cols-2">
        {plugins.map((p) => (
          <div key={p.name} className="rounded-xl border p-4"
               style={{ borderColor: "var(--athena-border)", background: "var(--athena-panel)" }}>
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <h3 className="font-medium">{p.display_name}</h3>
                {p.placeholder && (
                  <span className="rounded-full border px-2 py-0.5 text-[10px]"
                        style={{ borderColor: "var(--athena-border)", color: "var(--athena-dim)" }}>
                    placeholder
                  </span>
                )}
              </div>
              <label className="flex cursor-pointer items-center gap-2 text-xs"
                     style={{ color: "var(--athena-dim)" }}>
                {p.enabled ? "enabled" : "disabled"}
                <input
                  type="checkbox"
                  checked={p.enabled}
                  onChange={(e) =>
                    api.setPluginEnabled(p.name, e.target.checked).then(refresh)}
                  className="accent-sky-400"
                />
              </label>
            </div>
            <p className="mt-1 text-xs" style={{ color: "var(--athena-dim)" }}>{p.description}</p>
            {p.load_error && (
              <p className="mt-2 text-xs" style={{ color: "var(--athena-danger)" }}>
                Load error: {p.load_error}
              </p>
            )}
            <div className="mt-3 space-y-1.5">
              {p.tools.map((t) => (
                <div key={t.name} className="flex items-center gap-2 text-xs">
                  <span className="h-1.5 w-1.5 rounded-full"
                        style={{ background: PERM_COLOR[t.permission] ?? "var(--athena-dim)" }}
                        title={t.permission} />
                  <code>{t.name}</code>
                  <span className="truncate" style={{ color: "var(--athena-dim)" }}>
                    {t.description}
                  </span>
                  {t.implemented && p.name === "core" && t.name === "echo" && (
                    <button
                      onClick={() =>
                        api.executeTool("core", "echo", { text: "ping from UI" })
                          .then((r) => setNotice(`echo → ${JSON.stringify(r.result)}`))}
                      className="ml-auto shrink-0 rounded border px-2 py-0.5 text-[10px]"
                      style={{ borderColor: "var(--athena-border)" }}
                    >
                      test
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
