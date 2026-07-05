/** Global UI state (zustand). Server data stays in components; only
 * cross-view state lives here. */
import { create } from "zustand";
import type { OrbState, Workspace } from "@shared/types";

export type View =
  | "chat" | "memory" | "workspaces" | "plugins" | "health" | "logs" | "settings";

interface AppState {
  view: View;
  setView: (v: View) => void;
  orbState: OrbState;
  setOrbState: (s: OrbState) => void;
  workspaces: Workspace[];
  setWorkspaces: (w: Workspace[]) => void;
  activeWorkspaceId: string | null;
  setActiveWorkspaceId: (id: string | null) => void;
  backendUp: boolean | null; // null = unknown/checking
  setBackendUp: (up: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  view: "chat",
  setView: (view) => set({ view }),
  orbState: "idle",
  setOrbState: (orbState) => set({ orbState }),
  workspaces: [],
  setWorkspaces: (workspaces) => set({ workspaces }),
  activeWorkspaceId: null,
  setActiveWorkspaceId: (activeWorkspaceId) => set({ activeWorkspaceId }),
  backendUp: null,
  setBackendUp: (backendUp) => set({ backendUp }),
}));
