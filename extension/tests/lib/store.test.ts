/**
 * Tests for lib/store — Zustand UI store.
 */
import { beforeEach, describe, expect, it } from "vitest";

import {
  selectActiveSupplier,
  selectIsReady,
  usePopupStore,
  __test__,
} from "../../src/lib/store";

beforeEach(() => {
  usePopupStore.setState({ ...__test__.initialState });
});

describe("popup store", () => {
  it("starts in the default state", () => {
    const s = usePopupStore.getState();
    expect(s.screen).toBe("home");
    expect(s.tabId).toBeNull();
    expect(s.suppliers).toEqual([]);
    expect(s.vaultUnlocked).toBe(false);
  });

  it("setScreen updates the current screen", () => {
    usePopupStore.getState().setScreen("suppliers");
    expect(usePopupStore.getState().screen).toBe("suppliers");
  });

  it("setActiveSupplier and clearActiveSupplier maintain the per-tab map", () => {
    const s = usePopupStore.getState();
    s.setActiveSupplier(42, "sup1");
    expect(usePopupStore.getState().activeSupplierByTab[42]).toBe("sup1");
    s.clearActiveSupplier(42);
    expect(usePopupStore.getState().activeSupplierByTab[42]).toBeUndefined();
  });

  it("selectActiveSupplier resolves through current tabId", () => {
    const s = usePopupStore.getState();
    s.setTabId(7);
    s.setActiveSupplier(7, "supX");
    expect(selectActiveSupplier(usePopupStore.getState())).toBe("supX");
  });

  it("selectIsReady requires both connection and vault unlocked", () => {
    const s = usePopupStore.getState();
    expect(selectIsReady(usePopupStore.getState())).toBe(false);
    s.setHasConnection(true);
    s.setVaultUnlocked(true);
    expect(selectIsReady(usePopupStore.getState())).toBe(true);
  });
});
