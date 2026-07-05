/** System health: providers, database, voice, plugins, spend. */
import { useEffect, useState } from "react";
import { api } from "../lib/api";

function Dot({ ok }: { ok: boolean }) {
  return (
    <span className="inline-block h-2.5 w-2.5 rounded-full"
          style={{ background: ok ? "#34d399" : "var(--athena-danger)" }} />
  );
}

export default function HealthView() {
  const [health, setHealth] = useState<Record<string, any> | null>(null);
  const [usage, setUsage] = useState<{ month_spend_usd: number; history: any[] } | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    const load = () => {
      api.healthFull().then(setHealth).catch((e) => setErr(String(e)));
      api.usage().then(setUsage).catch(() => {});
    };
    load();
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
  }, []);

  if (err) return <p className="p-6 text-sm" style={{ color: "var(--athena-danger)" }}>{err}</p>;
  if (!health) return <p className="p-6 text-sm" style={{ color: "var(--athena-dim)" }}>Checking…</p>;

  return (
    <div className="h-full space-y-5 overflow-y-auto p-6">
      <h2 className="text-lg font-semibold">System health</h2>

      <section className="rounded-xl border p-4"
               style={{ borderColor: "var(--athena-border)", background: "var(--athena-panel)" }}>
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider"
            style={{ color: "var(--athena-dim)" }}>Model providers</h3>
        <div className="space-y-2">
          {health.providers?.map((p: any) => (
            <div key={p.name} className="flex items-center gap-3 text-sm">
              <Dot ok={p.available} />
              <span className="w-28 font-medium">{p.name}</span>
              <span className="rounded-full border px-2 py-0.5 text-[10px]"
                    style={{ borderColor: "var(--athena-border)", color: "var(--athena-dim)" }}>
                {p.kind}
              </span>
              <span className="truncate text-xs" style={{ color: "var(--athena-dim)" }}>
                {p.detail} {p.models?.length ? `· ${p.models.join(", ")}` : ""}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border p-4"
             style={{ borderColor: "var(--athena-border)", background: "var(--athena-panel)" }}>
          <h3 className="text-xs font-semibold uppercase tracking-wider"
              style={{ color: "var(--athena-dim)" }}>Database</h3>
          <div className="mt-2 flex items-center gap-2 text-sm">
            <Dot ok={health.database?.ok} />
            <span className="truncate text-xs">{health.database?.detail}</span>
          </div>
        </div>
        <div className="rounded-xl border p-4"
             style={{ borderColor: "var(--athena-border)", background: "var(--athena-panel)" }}>
          <h3 className="text-xs font-semibold uppercase tracking-wider"
              style={{ color: "var(--athena-dim)" }}>Voice pipeline</h3>
          <div className="mt-2 space-y-1 text-xs">
            {(["stt", "tts", "wake_word"] as const).map((k) => (
              <div key={k} className="flex items-center gap-2">
                <Dot ok={health.voice?.[k]?.available} />
                <span>{k}</span>
                <span style={{ color: "var(--athena-dim)" }}>
                  {health.voice?.[k]?.available ? health.voice[k].provider : health.voice?.[k]?.detail}
                </span>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-xl border p-4"
             style={{ borderColor: "var(--athena-border)", background: "var(--athena-panel)" }}>
          <h3 className="text-xs font-semibold uppercase tracking-wider"
              style={{ color: "var(--athena-dim)" }}>Premium spend (month)</h3>
          <p className="mt-2 text-2xl font-semibold" style={{ color: "var(--athena-premium)" }}>
            ${usage?.month_spend_usd?.toFixed(2) ?? "0.00"}
          </p>
          <p className="text-[10px]" style={{ color: "var(--athena-dim)" }}>
            {usage?.history?.length ?? 0} tracked requests
          </p>
        </div>
      </section>

      <section className="rounded-xl border p-4"
               style={{ borderColor: "var(--athena-border)", background: "var(--athena-panel)" }}>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider"
            style={{ color: "var(--athena-dim)" }}>Recent model calls</h3>
        <div className="space-y-1 text-xs">
          {usage?.history?.slice(0, 12).map((u: any) => (
            <div key={u.id} className="flex items-center gap-3">
              <span className="w-40 truncate font-medium">{u.provider}:{u.model}</span>
              <span style={{ color: "var(--athena-dim)" }}>{u.tokens_in}→{u.tokens_out} tok</span>
              <span style={{ color: "var(--athena-premium)" }}>
                {u.est_cost_usd > 0 ? `$${u.est_cost_usd.toFixed(4)}` : "free"}
              </span>
              <span className="truncate" style={{ color: "var(--athena-dim)" }} title={u.routing_reason}>
                {u.routing_reason}
              </span>
            </div>
          ))}
          {!usage?.history?.length && (
            <p style={{ color: "var(--athena-dim)" }}>No model calls yet.</p>
          )}
        </div>
      </section>
    </div>
  );
}
