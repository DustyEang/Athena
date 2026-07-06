/** Athena's presence. Size in px; state drives the animation class. */
import type { OrbState } from "@shared/types";

const LABEL: Record<OrbState, string> = {
  idle: "", listening: "listening…", thinking: "thinking…", speaking: "speaking…",
};

export default function Orb({ state, size = 96 }: { state: OrbState; size?: number }) {
  return (
    <div className="flex flex-col items-center gap-2">
      <div
        className={`orb orb-${state}`}
        style={{ width: size, height: size }}
        aria-label={`Athena is ${state}`}
      >
        <div className="orb-face">
          <div className="orb-eye orb-eye-left" />
          <div className="orb-eye orb-eye-right" />
        </div>
      </div>
      {LABEL[state] && (
        <span className="text-xs tracking-widest uppercase" style={{ color: "var(--athena-dim)" }}>
          {LABEL[state]}
        </span>
      )}
    </div>
  );
}
