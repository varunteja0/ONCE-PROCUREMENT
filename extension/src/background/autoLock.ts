/**
 * Idle-driven auto-lock.
 *
 * The vault keeps its own 15-minute timer (see `lib/vault.ts`) — that
 * runs only while the popup/service worker is alive and the unlock
 * happened in the same context. This module *additionally* watches
 * `chrome.idle` from the background and broadcasts a `vault.lock`
 * intent to every open popup whenever:
 *
 *  - the user's idle state transitions to `idle` or `locked`, AND
 *  - the elapsed-since-unlock exceeds the configured threshold.
 *
 * Threshold is read from `chrome.storage.local` under
 * `STORAGE_KEYS.autoLockMinutes` (defaults to 15).
 */

import { STORAGE_KEYS, storageGet } from "../lib/storage";

const DEFAULT_AUTO_LOCK_MIN = 15;

interface LockHooks {
  /** Called when this module decides the vault should lock. */
  lock: () => void | Promise<void>;
  /** Get current "vault unlocked at" wall-clock ms or null. */
  unlockedAt: () => number | null | Promise<number | null>;
  /** Optional clock for tests. */
  now?: () => number;
}

export async function getAutoLockMinutes(): Promise<number> {
  const v = await storageGet<number>(STORAGE_KEYS.autoLockMinutes, DEFAULT_AUTO_LOCK_MIN);
  if (typeof v !== "number" || !Number.isFinite(v) || v <= 0) {
    return DEFAULT_AUTO_LOCK_MIN;
  }
  // Clamp to [1, 240] minutes.
  return Math.min(240, Math.max(1, Math.floor(v)));
}

/**
 * Pure function — given the current idle state and elapsed minutes
 * since last unlock, decide whether to lock now.
 */
export function shouldLockNow(
  idleState: chrome.idle.IdleState,
  unlockedAt: number | null,
  thresholdMin: number,
  now: number,
): boolean {
  if (unlockedAt === null) return false;
  if (idleState === "active") return false;
  const elapsedMin = (now - unlockedAt) / 60_000;
  return elapsedMin >= thresholdMin;
}

export function registerIdleAutoLock(hooks: LockHooks): () => void {
  if (typeof chrome === "undefined" || !chrome.idle || !chrome.idle.onStateChanged) {
    return () => undefined;
  }
  // 60s polling threshold — minimum supported by chrome.idle.
  try {
    chrome.idle.setDetectionInterval(60);
  } catch {
    /* test env may not implement this */
  }
  const listener = async (state: chrome.idle.IdleState): Promise<void> => {
    const threshold = await getAutoLockMinutes();
    const now = (hooks.now ?? Date.now)();
    const unlockedAt = await hooks.unlockedAt();
    if (shouldLockNow(state, unlockedAt, threshold, now)) {
      await hooks.lock();
    }
  };
  const wrapped = (state: chrome.idle.IdleState): void => {
    void listener(state);
  };
  chrome.idle.onStateChanged.addListener(wrapped);
  return () => chrome.idle.onStateChanged.removeListener(wrapped);
}

export const __test__ = { DEFAULT_AUTO_LOCK_MIN };
