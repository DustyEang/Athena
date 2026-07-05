/** Chat: streaming responses, routing transparency, tool activity feed,
 * premium-model confirmation, model override selector. */
import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatEvent, ModelOption, RoutingEvent, ToolActivity, ToolRun, Usage } from "@shared/types";
import Orb from "../components/Orb";
import { api, streamChat, transcribeAudio } from "../lib/api";
import { useAppStore } from "../lib/store";

interface UiMessage {
  role: "user" | "assistant";
  content: string;
  routing?: RoutingEvent;
  usage?: Usage;
  error?: string;
  tools?: ToolActivity[]; // agent-loop tool calls rendered inline
}

const TOOL_STATUS_COLOR: Record<string, string> = {
  running: "var(--athena-tool)",
  ok: "#34d399",
  error: "var(--athena-danger)",
  denied: "var(--athena-dim)",
  pending_confirmation: "var(--athena-tool)",
};

const TIER_COLOR: Record<string, string> = {
  local: "var(--athena-core)",
  premium: "var(--athena-premium)",
  mock: "var(--athena-dim)",
};

export default function ChatView() {
  const { orbState, setOrbState, activeWorkspaceId } = useAppStore();
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [modelOverride, setModelOverride] = useState("");
  const [models, setModels] = useState<ModelOption[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [premiumPrompt, setPremiumPrompt] = useState<{ message: string; model: string } | null>(null);
  const [toolRuns, setToolRuns] = useState<ToolRun[]>([]);
  const [voiceReady, setVoiceReady] = useState(false);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.models().then(setModels).catch(() => {});
    api.voiceStatus().then((s) => setVoiceReady(!!s.stt?.available)).catch(() => {});
    const t = setInterval(() => api.toolRuns().then(setToolRuns).catch(() => {}), 5000);
    api.toolRuns().then(setToolRuns).catch(() => {});
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages]);

  const send = useCallback(
    async (text: string, confirmPremium = false) => {
      if (!text.trim() || busy) return;
      setBusy(true);
      setOrbState("thinking");
      setPremiumPrompt(null);
      setMessages((m) => [...m, { role: "user", content: text }, { role: "assistant", content: "" }]);

      const update = (fn: (last: UiMessage) => UiMessage) =>
        setMessages((m) => [...m.slice(0, -1), fn(m[m.length - 1])]);

      try {
        await streamChat(
          {
            message: text,
            conversation_id: conversationId,
            workspace_id: activeWorkspaceId,
            model_override: modelOverride || null,
            confirm_premium: confirmPremium,
          },
          (e: ChatEvent) => {
            if (e.type === "routing") {
              setConversationId(e.conversation_id);
              update((last) => ({ ...last, routing: e }));
            } else if (e.type === "premium_confirmation_required") {
              // Remove the empty assistant bubble; ask the user instead.
              setMessages((m) => m.slice(0, -2));
              setPremiumPrompt({ message: text, model: e.model });
            } else if (e.type === "delta") {
              setOrbState("speaking");
              update((last) => ({ ...last, content: last.content + e.text }));
            } else if (e.type === "tool_call") {
              setOrbState("thinking");
              update((last) => ({
                ...last,
                tools: [...(last.tools ?? []), {
                  call_id: e.call_id, plugin: e.plugin, tool: e.tool, status: "running",
                }],
              }));
            } else if (e.type === "tool_result") {
              update((last) => ({
                ...last,
                tools: (last.tools ?? []).map((t) =>
                  t.call_id === e.call_id ? { ...t, status: e.status, preview: e.preview } : t),
              }));
              api.toolRuns().then(setToolRuns).catch(() => {});
            } else if (e.type === "done") {
              update((last) => ({ ...last, usage: e.usage }));
            } else if (e.type === "error") {
              update((last) => ({ ...last, error: e.message }));
            }
          },
        );
      } catch (err) {
        update((last) => ({ ...last, error: String(err) }));
      } finally {
        setBusy(false);
        setOrbState("idle");
      }
    },
    [busy, conversationId, activeWorkspaceId, modelOverride, setOrbState],
  );

  const startRecording = useCallback(async () => {
    if (recording || transcribing || busy) return;
    setVoiceError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      chunksRef.current = [];
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setOrbState("thinking");
        setTranscribing(true);
        try {
          const blob = new Blob(chunksRef.current, { type: rec.mimeType || "audio/webm" });
          if (blob.size > 0) {
            const text = await transcribeAudio(blob);
            if (text) setInput((prev) => (prev ? `${prev} ${text}` : text));
          }
        } catch (err) {
          setVoiceError(String(err));
        } finally {
          setTranscribing(false);
          setOrbState("idle");
        }
      };
      rec.start();
      recorderRef.current = rec;
      setRecording(true);
      setOrbState("listening");
    } catch {
      setVoiceError("Microphone access denied — allow the mic in your browser and try again.");
    }
  }, [recording, transcribing, busy, setOrbState]);

  const stopRecording = useCallback(() => {
    const rec = recorderRef.current;
    if (rec && rec.state !== "inactive") rec.stop();
    setRecording(false);
  }, []);

  const pending = toolRuns.filter((r) => r.status === "pending_confirmation");

  return (
    <div className="flex h-full">
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Header: orb + model selector */}
        <header
          className="flex items-center justify-between border-b px-6 py-3"
          style={{ borderColor: "var(--athena-border)" }}
        >
          <Orb state={orbState} size={44} />
          <div className="flex items-center gap-2 text-xs">
            <span style={{ color: "var(--athena-dim)" }}>Model</span>
            <select
              value={modelOverride}
              onChange={(e) => setModelOverride(e.target.value)}
              className="rounded-md border bg-transparent px-2 py-1.5"
              style={{ borderColor: "var(--athena-border)" }}
            >
              <option value="" style={{ background: "var(--athena-panel)" }}>
                Auto (Athena decides)
              </option>
              {models.map((m) => (
                <option
                  key={m.id}
                  value={m.id}
                  disabled={!m.available}
                  style={{ background: "var(--athena-panel)" }}
                >
                  {m.id} {m.kind === "premium" ? "💎" : ""} {m.available ? "" : "(offline)"}
                </option>
              ))}
            </select>
          </div>
        </header>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-6 py-4">
          {messages.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center gap-6 text-center">
              <Orb state="idle" size={140} />
              <div>
                <p className="text-lg">I'm listening.</p>
                <p className="mt-1 text-sm" style={{ color: "var(--athena-dim)" }}>
                  Simple chats stay on local models. Hard problems can escalate to
                  Fable 5 — with your approval.
                </p>
              </div>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className="max-w-[75%] rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap"
                style={{
                  background: m.role === "user" ? "rgba(56,189,248,0.12)" : "var(--athena-panel)",
                  border: `1px solid ${m.role === "user" ? "rgba(56,189,248,0.25)" : "var(--athena-border)"}`,
                }}
              >
                {m.routing && (
                  <div
                    className="mb-2 flex flex-wrap items-center gap-2 text-[11px]"
                    title={m.routing.reason}
                  >
                    <span
                      className="rounded-full px-2 py-0.5 font-medium"
                      style={{
                        color: TIER_COLOR[m.routing.tier] ?? "var(--athena-dim)",
                        border: `1px solid ${TIER_COLOR[m.routing.tier] ?? "var(--athena-border)"}`,
                      }}
                    >
                      {m.routing.provider}:{m.routing.model}
                    </span>
                    <span style={{ color: "var(--athena-dim)" }}>{m.routing.reason}</span>
                  </div>
                )}
                {(m.tools ?? []).length > 0 && (
                  <div className="mb-2 space-y-1">
                    {m.tools!.map((t) => (
                      <div key={t.call_id} className="flex items-center gap-2 text-[11px]"
                           title={t.preview ?? ""}>
                        <span className="rounded-full border px-2 py-0.5"
                              style={{
                                color: TOOL_STATUS_COLOR[t.status] ?? "var(--athena-dim)",
                                borderColor: TOOL_STATUS_COLOR[t.status] ?? "var(--athena-border)",
                              }}>
                          ⚙ {t.plugin}.{t.tool}
                        </span>
                        <span style={{ color: "var(--athena-dim)" }}>
                          {t.status === "running" ? "running…"
                            : t.status === "pending_confirmation" ? "awaiting your approval →"
                            : t.status}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
                {m.content || (m.role === "assistant" && !m.error && busy && i === messages.length - 1 ? "…" : m.content)}
                {m.error && (
                  <div className="mt-2 text-xs" style={{ color: "var(--athena-danger)" }}>
                    ⚠ {m.error}
                  </div>
                )}
                {m.usage && (
                  <div className="mt-2 text-[10px]" style={{ color: "var(--athena-dim)" }}>
                    {m.usage.tokens_in}→{m.usage.tokens_out} tok
                    {m.usage.est_cost_usd > 0 && ` · $${m.usage.est_cost_usd.toFixed(4)}`}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Premium confirmation */}
        {premiumPrompt && (
          <div
            className="mx-6 mb-3 flex items-center justify-between gap-4 rounded-xl border px-4 py-3 text-sm"
            style={{ borderColor: "var(--athena-premium)", background: "rgba(167,139,250,0.08)" }}
          >
            <span>
              This looks like high-value work. Use premium model{" "}
              <b style={{ color: "var(--athena-premium)" }}>{premiumPrompt.model}</b>? (costs tokens)
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => send(premiumPrompt.message, true)}
                className="rounded-lg px-3 py-1.5 font-medium"
                style={{ background: "var(--athena-premium)", color: "#0b1120" }}
              >
                Use premium
              </button>
              <button
                onClick={() => {
                  const msg = premiumPrompt.message;
                  setPremiumPrompt(null);
                  setModelOverride("");
                  // fall back to explicit local routing via task-mode nothing needed:
                  send(msg + "\n\n(Use a local model for this.)", false);
                }}
                className="rounded-lg border px-3 py-1.5"
                style={{ borderColor: "var(--athena-border)" }}
              >
                Stay local
              </button>
            </div>
          </div>
        )}

        {/* Composer */}
        <div className="border-t px-6 py-4" style={{ borderColor: "var(--athena-border)" }}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const text = input;
              setInput("");
              send(text);
            }}
            className="flex gap-3"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={busy ? "Athena is responding…" : "Talk to Athena…"}
              disabled={busy}
              className="flex-1 rounded-xl border bg-transparent px-4 py-3 text-sm outline-none focus:border-sky-500/60"
              style={{ borderColor: "var(--athena-border)" }}
            />
            <button
              type="submit"
              disabled={busy || !input.trim()}
              className="rounded-xl px-5 py-3 text-sm font-medium disabled:opacity-40"
              style={{ background: "var(--athena-core)", color: "#06121f" }}
            >
              Send
            </button>
            <button
              type="button"
              title={
                !voiceReady
                  ? "Voice not configured — install faster-whisper (see docs/VOICE.md)"
                  : recording
                    ? "Release to transcribe"
                    : "Hold to talk"
              }
              disabled={!voiceReady || busy || transcribing}
              onMouseDown={startRecording}
              onMouseUp={stopRecording}
              onMouseLeave={() => recording && stopRecording()}
              onTouchStart={(e) => {
                e.preventDefault();
                startRecording();
              }}
              onTouchEnd={(e) => {
                e.preventDefault();
                stopRecording();
              }}
              className="rounded-xl border px-4 py-3 text-sm select-none disabled:opacity-40"
              style={{
                borderColor: recording ? "var(--athena-danger)" : "var(--athena-border)",
                background: recording ? "rgba(248,113,113,0.15)" : "transparent",
                opacity: voiceReady ? 1 : 0.5,
              }}
            >
              {transcribing ? "⏳" : recording ? "🔴" : "🎙"}
            </button>
          </form>
          {voiceError && (
            <div className="mt-2 text-xs" style={{ color: "var(--athena-danger)" }}>
              ⚠ {voiceError}
            </div>
          )}
        </div>
      </div>

      {/* Tool activity feed */}
      <aside
        className="hidden w-72 flex-col border-l lg:flex"
        style={{ borderColor: "var(--athena-border)", background: "var(--athena-panel)" }}
      >
        <h3 className="px-4 pb-2 pt-4 text-xs font-semibold uppercase tracking-wider"
            style={{ color: "var(--athena-dim)" }}>
          Tool activity
        </h3>
        <div className="flex-1 space-y-2 overflow-y-auto px-3 pb-4">
          {pending.map((r) => (
            <div key={r.id} className="rounded-lg border p-3 text-xs"
                 style={{ borderColor: "var(--athena-tool)", background: "rgba(251,191,36,0.07)" }}>
              <div className="font-medium" style={{ color: "var(--athena-tool)" }}>
                Confirmation needed
              </div>
              <div className="mt-1">{r.plugin}.{r.tool}</div>
              <div className="mt-1 break-all opacity-70">{JSON.stringify(r.args)}</div>
              <div className="mt-2 flex gap-2">
                <button
                  onClick={() => api.confirmTool(r.id, true).then(() => api.toolRuns().then(setToolRuns))}
                  className="rounded px-2 py-1 font-medium"
                  style={{ background: "var(--athena-tool)", color: "#1c1917" }}
                >
                  Approve
                </button>
                <button
                  onClick={() => api.confirmTool(r.id, false).then(() => api.toolRuns().then(setToolRuns))}
                  className="rounded border px-2 py-1"
                  style={{ borderColor: "var(--athena-border)" }}
                >
                  Deny
                </button>
              </div>
            </div>
          ))}
          {toolRuns.filter((r) => r.status !== "pending_confirmation").map((r) => (
            <div key={r.id} className="rounded-lg border p-2.5 text-xs"
                 style={{ borderColor: "var(--athena-border)" }}>
              <div className="flex items-center justify-between">
                <span>{r.plugin}.{r.tool}</span>
                <span style={{
                  color: r.status === "ok" ? "#34d399"
                    : r.status === "error" ? "var(--athena-danger)" : "var(--athena-dim)",
                }}>
                  {r.status}
                </span>
              </div>
              {r.error && <div className="mt-1 opacity-70">{r.error.slice(0, 120)}</div>}
            </div>
          ))}
          {toolRuns.length === 0 && (
            <p className="px-1 text-xs" style={{ color: "var(--athena-dim)" }}>
              No tool activity yet. Try the echo tool from the Plugins screen.
            </p>
          )}
        </div>
      </aside>
    </div>
  );
}
