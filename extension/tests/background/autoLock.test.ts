/**
 * Tests for background/autoLock — pure shouldLockNow + getAutoLockMinutes clamping.
 */
import { describe, expect, it } from "vitest";

import { getAutoLockMinutes, shouldLockNow } from "../../src/background/autoLock";
import { STORAGE_KEYS } from "../../src/lib/storage";

describe("shouldLockNow", () => {
  const now = 1_700_000_000_000;
  const threshold = 15;

  it("returns false when never unlocked", () => {
    expect(shouldLockNow("idle", null, threshold, now)).toBe(false);
  });

  it("returns false when state is active", () => {
    expect(shouldLockNow("active", now - 60 * 60_000, threshold, now)).toBe(
      false,
    );
  });

  it("returns false when elapsed < threshold", () => {
    expect(shouldLockNow("idle", now - 5 * 60_000, threshold, now)).toBe(false);
  });

  it("returns true when idle and elapsed >= threshold", () => {
    expect(shouldLockNow("idle", now - 16 * 60_000, threshold, now)).toBe(true);
  });

  it("returns true when locked and elapsed >= threshold", () => {
    expect(shouldLockNow("locked", now - 20 * 60_000, threshold, now)).toBe(
      true,
    );
  });
});

describe("getAutoLockMinutes", () => {
  it("returns the default when unset", async () => {
    expect(await getAutoLockMinutes()).toBe(15);
  });

  it("clamps below 1 to 1", async () => {
    await chrome.storage.local.set({ [STORAGE_KEYS.autoLockMinutes]: 0 });
    expect(await getAutoLockMinutes()).toBe(15);
    await chrome.storage.local.set({ [STORAGE_KEYS.autoLockMinutes]: -5 });
    expect(await getAutoLockMinutes()).toBe(15);
  });

  it("clamps above 240 to 240", async () => {
    await chrome.storage.local.set({ [STORAGE_KEYS.autoLockMinutes]: 9999 });
    expect(await getAutoLockMinutes()).toBe(240);
  });

  it("returns configured value within range", async () => {
    await chrome.storage.local.set({ [STORAGE_KEYS.autoLockMinutes]: 30 });
    expect(await getAutoLockMinutes()).toBe(30);
  });
});
