import { create } from "zustand";
import { persist } from "zustand/middleware";

export type AuditorProfileSummary = {
  id: string;
  fullName: string;
  occupation: string;
  taxYear: string;
  tin: string;
};

export type PendingTransactionBreakdownLine = {
  classKey: string;
  amount: number;
};

type AuditorWorkspaceState = {
  /** Selected taxpayer profile — shared across all auditor modules. */
  activeProfileId: string | null;
  /** When locked, profile selection is pinned until the auditor unlocks. */
  isLocked: boolean;
  /** Cached display fields for the right panel (avoid refetch on every navigation). */
  profileSummary: AuditorProfileSummary | null;
  /** Taxable inflow buckets from transaction classification, awaiting OE merge. */
  pendingTransactionBreakdown: PendingTransactionBreakdownLine[] | null;
  /** Right-hand auditor panel collapsed to a slim rail (desktop). */
  isPanelCollapsed: boolean;
  setActiveProfile: (id: string | null, summary?: AuditorProfileSummary | null) => void;
  setProfileSummary: (summary: AuditorProfileSummary | null) => void;
  setLocked: (locked: boolean) => void;
  setPendingTransactionBreakdown: (lines: PendingTransactionBreakdownLine[] | null) => void;
  setPanelCollapsed: (collapsed: boolean) => void;
  clearProfile: () => void;
};

export const useAuditorWorkspaceStore = create<AuditorWorkspaceState>()(
  persist(
    (set) => ({
      activeProfileId: null,
      isLocked: false,
      profileSummary: null,
      pendingTransactionBreakdown: null,
      isPanelCollapsed: false,
      setActiveProfile: (id, summary) =>
        set((state) => ({
          activeProfileId: id,
          profileSummary: summary ?? null,
          pendingTransactionBreakdown:
            id === state.activeProfileId ? state.pendingTransactionBreakdown : null,
          isPanelCollapsed: id ? true : false,
        })),
      setProfileSummary: (summary) => set({ profileSummary: summary }),
      setLocked: (locked) =>
        set((state) => ({
          isLocked: locked,
          isPanelCollapsed: locked && state.activeProfileId ? true : state.isPanelCollapsed,
        })),
      setPendingTransactionBreakdown: (lines) => set({ pendingTransactionBreakdown: lines }),
      setPanelCollapsed: (collapsed) => set({ isPanelCollapsed: collapsed }),
      clearProfile: () =>
        set({
          activeProfileId: null,
          profileSummary: null,
          isLocked: false,
          pendingTransactionBreakdown: null,
          isPanelCollapsed: false,
        }),
    }),
    { name: "auditor-workspace" },
  ),
);
