/**
 * Popup-side Zustand store.
 *
 * Holds ephemeral UI state (current screen, active supplier per tab,
 * draft passphrase) — every "persisted" value (tokens, vault salt,
 * auto-lock minutes) lives in `chrome.storage.local` and is read through
 * the typed wrappers in `lib/storage.ts`. The store is intentionally
 * thin so test setup is trivial and reloads can rebuild from storage.
 */

import { create } from "zustand";

import type { PortalDetection } from "./messaging";
import type { SupplierListItem } from "./api";

export type Screen =
  | "setup"
  | "locked"
  | "home"
  | "suppliers"
  | "submissions"
  | "receipts"
  | "activity"
  | "settings";

export interface PopupState {
  screen: Screen;
  /** Current tab id, set on mount via chrome.tabs.query. */
  tabId: number | null;
  /** Most recent portal detection for the current tab. */
  detection: PortalDetection | null;
  /** Cached supplier list (mirror of last sync). */
  suppliers: SupplierListItem[];
  /** Map of tabId → supplierId chosen by the user. */
  activeSupplierByTab: Record<number, string>;
  /** Snapshot of vault unlocked state (refreshed by App on mount). */
  vaultUnlocked: boolean;
  /** Has the user run the first-time setup yet? */
  hasConnection: boolean;
  /** Toast-equivalent banner for in-popup transient errors. */
  banner: { kind: "info" | "error" | "success"; text: string } | null;

  // ---- actions -----------------------------------------------------------
  setScreen: (s: Screen) => void;
  setTabId: (id: number | null) => void;
  setDetection: (d: PortalDetection | null) => void;
  setSuppliers: (s: SupplierListItem[]) => void;
  setActiveSupplier: (tabId: number, supplierId: string) => void;
  clearActiveSupplier: (tabId: number) => void;
  setVaultUnlocked: (u: boolean) => void;
  setHasConnection: (c: boolean) => void;
  setBanner: (b: PopupState["banner"]) => void;
  reset: () => void;
}

const initialState = {
  screen: "home" as Screen,
  tabId: null,
  detection: null,
  suppliers: [] as SupplierListItem[],
  activeSupplierByTab: {} as Record<number, string>,
  vaultUnlocked: false,
  hasConnection: false,
  banner: null as PopupState["banner"],
};

export const usePopupStore = create<PopupState>((set) => ({
  ...initialState,

  setScreen: (screen) => set({ screen }),
  setTabId: (tabId) => set({ tabId }),
  setDetection: (detection) => set({ detection }),
  setSuppliers: (suppliers) => set({ suppliers }),
  setActiveSupplier: (tabId, supplierId) =>
    set((s) => ({
      activeSupplierByTab: { ...s.activeSupplierByTab, [tabId]: supplierId },
    })),
  clearActiveSupplier: (tabId) =>
    set((s) => {
      const next = { ...s.activeSupplierByTab };
      delete next[tabId];
      return { activeSupplierByTab: next };
    }),
  setVaultUnlocked: (vaultUnlocked) => set({ vaultUnlocked }),
  setHasConnection: (hasConnection) => set({ hasConnection }),
  setBanner: (banner) => set({ banner }),
  reset: () => set({ ...initialState }),
}));

/**
 * Selectors — used to keep render-on-change tight.
 */
export const selectActiveSupplier = (s: PopupState): string | null => {
  if (s.tabId === null) return null;
  return s.activeSupplierByTab[s.tabId] ?? null;
};

export const selectIsReady = (s: PopupState): boolean =>
  s.hasConnection && s.vaultUnlocked;

export const __test__ = {
  initialState,
};
