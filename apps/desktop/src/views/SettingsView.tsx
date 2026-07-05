/** Settings: everything user-tunable, persisted in the backend DB.
 * API keys are env-only — this screen shows configured/not, never values. */
import { useEffect, useState } from "react";
import { api } from "../lib/api";

type SettingsMap = Record<string, any>;

export default function SettingsView() {
  const [settings, setSettings] = useState<SettingsMap | null>(null);
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.getSettings().then(setSettings).catch((e) => setErr(String(e)));
  }, []);

  if (err) return <p className="p-6 text-sm" style={{ color: "var(--athena-danger)" }}>{err}</p>;
  if (!settings) return <p className="p-6 text-sm" style={{ color: "var(--athena-dim)" }}>Loading…</p>;

  const set = (key: string, value: any) => {
    setSettings({ ...settings, [key]: value });
    setSaved(false);
  };
  const save = () => {
    const { _env, ...values } = settings;
    api.putSettings(values).then(() => setSaved(true)).catch((e) => setErr(String(e)));
  };

  const Row = ({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) => (
    <div className="flex items-center justify-between gap-6 py-3"
         style={{ borderBottom: "1px solid var(--athena-border)" }}>
      <div>
        <p className="text-sm">{label}</p>
        {hint && <p className="text-xs" style={{ color: "var(--athena-dim)" }}>{hint}</p>}
      </div>
      {children}
    </div>
  );
  const Select = ({ k, options }: { k: string; options: string[] }) => (
    <select value={settings[k]} onChange={(e) => set(k, e.target.value)}
            className="rounded-lg border bg-transparent px-2 py-1.5 text-sm"
            style={{ borderColor: "var(--athena-border)" }}>
      {options.map((o) => (
        <option key={o} value={o} style={{ background: "var(--athena-panel)" }}>{o}</option>
      ))}
    </select>
  );
  const Toggle = ({ k }: { k: string }) => (
    <input type="checkbox" checked={!!settings[k]} onChange={(e) => set(k, e.target.checked)}
           className="h-4 w-4 accent-sky-400" />
  );

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Settings</h2>
          <button onClick={save} className="rounded-lg px-4 py-2 text-sm font-medium"
                  style={{ background: "var(--athena-core)", color: "#06121f" }}>
            {saved ? "Saved ✓" : "Save changes"}
          </button>
        </div>

        <h3 className="mt-6 text-xs font-semibold uppercase tracking-wider"
            style={{ color: "var(--athena-dim)" }}>Models & cost</h3>
        <Row label="Task mode" hint="cheap = never premium · balanced = classifier decides · max_power = prefer premium">
          <Select k="task_mode" options={["cheap", "balanced", "max_power"]} />
        </Row>
        <Row label="Ask before premium model" hint="Athena requests approval before spending premium tokens">
          <Toggle k="ask_before_premium" />
        </Row>
        <Row label="Monthly budget (USD)" hint="Premium routing stops at this limit">
          <input type="number" min={0} step={1} value={settings.budget_monthly_usd}
                 onChange={(e) => set("budget_monthly_usd", Number(e.target.value))}
                 className="w-24 rounded-lg border bg-transparent px-2 py-1.5 text-sm text-right"
                 style={{ borderColor: "var(--athena-border)" }} />
        </Row>
        <Row label="Fable 5 API key"
             hint={settings._env?.fable5_configured
               ? "Configured via environment (.env)"
               : "Not configured — set ATHENA_FABLE5_API_KEY in .env (never stored in the app)"}>
          <span className="text-xs" style={{
            color: settings._env?.fable5_configured ? "#34d399" : "var(--athena-dim)" }}>
            {settings._env?.fable5_configured ? "● configured" : "○ not set"}
          </span>
        </Row>

        <h3 className="mt-8 text-xs font-semibold uppercase tracking-wider"
            style={{ color: "var(--athena-dim)" }}>Memory</h3>
        <Row label="Memory mode"
             hint="off · ask (propose, you approve) · auto_important · project_only · full">
          <Select k="memory_mode" options={["off", "ask", "auto_important", "project_only", "full"]} />
        </Row>

        <h3 className="mt-8 text-xs font-semibold uppercase tracking-wider"
            style={{ color: "var(--athena-dim)" }}>Agent</h3>
        <Row label="Tool use in chat"
             hint="Let the model call tools mid-conversation (sensitive tools still require your approval)">
          <Toggle k="agent_tools_enabled" />
        </Row>

        <h3 className="mt-8 text-xs font-semibold uppercase tracking-wider"
            style={{ color: "var(--athena-dim)" }}>Voice</h3>
        <Row label="Voice enabled" hint="Requires local STT/TTS install — see docs/VOICE.md">
          <Toggle k="voice_enabled" />
        </Row>
        <Row label='Wake word ("Athena")' hint="Placeholder — push-to-talk ships first">
          <Toggle k="wake_word_enabled" />
        </Row>

        <h3 className="mt-8 text-xs font-semibold uppercase tracking-wider"
            style={{ color: "var(--athena-dim)" }}>Appearance & app</h3>
        <Row label="Theme"><Select k="theme" options={["dark"]} /></Row>
        <Row label="Orb behavior"><Select k="orb_behavior" options={["ambient", "minimal", "off"]} /></Row>
        <Row label="Debug mode"><Toggle k="debug_mode" /></Row>
        <Row label="Server mode"
             hint="local today; server_assisted / cloud_orchestrated are roadmap (docs/SERVER_ROADMAP.md)">
          <Select k="server_mode" options={["local", "server_assisted", "cloud_orchestrated"]} />
        </Row>
        <Row label="App launcher allowlist" hint="Comma-separated app names the launcher may start">
          <input value={(settings.app_launcher_allowlist ?? []).join(", ")}
                 onChange={(e) => set("app_launcher_allowlist",
                   e.target.value.split(",").map((s) => s.trim()).filter(Boolean))}
                 className="w-64 rounded-lg border bg-transparent px-2 py-1.5 text-sm"
                 style={{ borderColor: "var(--athena-border)" }} />
        </Row>
      </div>
    </div>
  );
}
