/**
 * Typed thin wrapper around `chrome.storage.local`.
 *
 * Centralises the storage-key namespace used by the extension so that
 * background, popup and content scripts agree on key names and types.
 *
 * The key names match those used in `extension/src/background/index.ts`.
 */

export const STORAGE_KEYS = {
  apiBase: "once.apiBase",
  access: "once.access",
  refresh: "once.refresh",
  vaultSalt: "once.vault.salt",
  vaultInitialized: "once.vault.initialized",
  autoLockMinutes: "once.autoLockMinutes",
  defaultSupplierPerPortal: "once.defaultSupplierPerPortal",
  vaultUnlockedAt: "once.vaultUnlockedAt",
} as const;

export type StorageKey = (typeof STORAGE_KEYS)[keyof typeof STORAGE_KEYS];

export const DEFAULT_API_BASE = "http://localhost:8000";

export interface TokenPair {
  access: string;
  refresh: string;
}

// ---------------------------------------------------------------------------
// Low-level chrome.storage.local helpers
// ---------------------------------------------------------------------------

function ensureChromeStorage(): chrome.storage.LocalStorageArea {
  if (
    typeof chrome === "undefined" ||
    !chrome.storage ||
    !chrome.storage.local
  ) {
    throw new Error("chrome.storage.local is unavailable in this context");
  }
  return chrome.storage.local;
}

export async function storageGet<T>(
  key: string,
  fallback: T,
): Promise<T> {
  const area = ensureChromeStorage();
  const got = await area.get({ [key]: fallback });
  const value = got[key];
  return value === undefined ? fallback : (value as T);
}

export async function storageGetOptional<T>(
  key: string,
): Promise<T | null> {
  const area = ensureChromeStorage();
  const got = await area.get(key);
  const value = got[key];
  return value === undefined || value === null ? null : (value as T);
}

export async function storageSet(
  key: string,
  value: unknown,
): Promise<void> {
  const area = ensureChromeStorage();
  await area.set({ [key]: value });
}

export async function storageRemove(key: string): Promise<void> {
  const area = ensureChromeStorage();
  await area.remove(key);
}

// ---------------------------------------------------------------------------
// API base
// ---------------------------------------------------------------------------

export async function getApiBase(): Promise<string> {
  const v = await storageGet<string>(STORAGE_KEYS.apiBase, DEFAULT_API_BASE);
  if (typeof v === "string" && v.length > 0) return v.replace(/\/+$/, "");
  return DEFAULT_API_BASE;
}

export async function setApiBase(base: string): Promise<void> {
  if (typeof base !== "string" || base.length === 0) {
    throw new Error("setApiBase: base must be a non-empty string");
  }
  await storageSet(STORAGE_KEYS.apiBase, base.replace(/\/+$/, ""));
}

// ---------------------------------------------------------------------------
// JWT tokens
// ---------------------------------------------------------------------------

export async function getTokens(): Promise<TokenPair | null> {
  const access = await storageGetOptional<string>(STORAGE_KEYS.access);
  const refresh = await storageGetOptional<string>(STORAGE_KEYS.refresh);
  if (!access || !refresh) return null;
  return { access, refresh };
}

export async function setTokens(tokens: TokenPair): Promise<void> {
  if (
    !tokens ||
    typeof tokens.access !== "string" ||
    typeof tokens.refresh !== "string" ||
    tokens.access.length === 0 ||
    tokens.refresh.length === 0
  ) {
    throw new Error("setTokens: invalid token pair");
  }
  const area = ensureChromeStorage();
  await area.set({
    [STORAGE_KEYS.access]: tokens.access,
    [STORAGE_KEYS.refresh]: tokens.refresh,
  });
}

export async function clearTokens(): Promise<void> {
  const area = ensureChromeStorage();
  await area.remove([STORAGE_KEYS.access, STORAGE_KEYS.refresh]);
}
