/**
 * Background service worker for the Once extension (MV3).
 *
 * Responsibilities
 * ----------------
 *  - Type-routed message bus (see `lib/messaging.ts`):
 *      vault.* | portal.* | submission.* | sync.* | api.call | auth.*
 *      | activity.*
 *  - `chrome.tabs.onUpdated` → URL-based portal detection → badge update
 *    + cached detection per tabId.
 *  - `chrome.alarms` for: periodic sync (5m), pending retry (30s), lock
 *    check (1m).
 *  - `chrome.idle` → broadcast vault-lock when user has been away longer
 *    than the configured threshold.
 *  - Centralised fetch with single-in-flight refresh on 401.
 *
 * Constraints
 * -----------
 *  - No DOM access. No `new Function`, no `eval`. Vault unlock is NOT
 *    persisted to disk; the popup owns the SessionKey. Background is a
 *    pure transport for API + portal detection + alarm scheduling.
 */

import { append as appendActivity, list as listActivity, newId as newActivityId } from "../lib/activity";
import { routeMessages, type HandlerMap, type Message, type PortalDetection, type SyncStatus } from "../lib/messaging";
import { STORAGE_KEYS, storageGet, storageGetOptional, storageRemove, storageSet } from "../lib/storage";
import { drainPending, getStatus as getSyncStatus, queueSubmission, syncNow } from "../lib/sync";
import type { PortalPlatform } from "../types/portal";
import { getAutoLockMinutes, registerIdleAutoLock } from "./autoLock";
import { detectFromUrl, htmlHash, PORTAL_BADGES } from "./portalDetector";

// ---------------------------------------------------------------------------
// Alarms
// ---------------------------------------------------------------------------

const ALARM_SYNC = "once.sync";
const ALARM_RETRY = "once.retry";
const ALARM_LOCK = "once.lock";

function registerAlarms(): void {
  chrome.alarms.create(ALARM_SYNC, { periodInMinutes: 5 });
  chrome.alarms.create(ALARM_RETRY, { periodInMinutes: 0.5 });
  chrome.alarms.create(ALARM_LOCK, { periodInMinutes: 1 });

  chrome.alarms.onAlarm.addListener((alarm) => {
    switch (alarm.name) {
      case ALARM_SYNC:
        void syncNow().catch((err: unknown) => console.warn("[once.bg] sync failed", err));
        return;
      case ALARM_RETRY:
        void drainPending().catch((err: unknown) => console.warn("[once.bg] drain failed", err));
        return;
      case ALARM_LOCK:
        void maybeAutoLock();
        return;
      default:
        return;
    }
  });
}

async function maybeAutoLock(): Promise<void> {
  const unlockedAt = await storageGet<number | null>(STORAGE_KEYS.vaultUnlockedAt, null);
  if (!unlockedAt) return;
  const threshold = await getAutoLockMinutes();
  const elapsed = (Date.now() - unlockedAt) / 60_000;
  if (elapsed >= threshold) {
    await broadcastLock();
  }
}

async function broadcastLock(): Promise<void> {
  await storageRemove(STORAGE_KEYS.vaultUnlockedAt);
  // Best-effort: tell every open popup/options page to drop in-memory state.
  try {
    await chrome.runtime.sendMessage({ type: "vault.lock" } satisfies Message);
  } catch {
    /* no listener — fine */
  }
}

// ---------------------------------------------------------------------------
// Per-tab detection cache
// ---------------------------------------------------------------------------

const detectionByTab = new Map<number, PortalDetection>();

async function onTabUpdated(tabId: number, changeInfo: chrome.tabs.TabChangeInfo, tab: chrome.tabs.Tab): Promise<void> {
  // Only react to URL changes / completed loads.
  if (!changeInfo.url && changeInfo.status !== "complete") return;
  const url = changeInfo.url ?? tab.url;
  if (!url) {
    detectionByTab.delete(tabId);
    await setBadge(tabId, "", "#475569");
    return;
  }
  const result = detectFromUrl(url);
  if (!result) {
    detectionByTab.delete(tabId);
    await setBadge(tabId, "", "#475569");
    return;
  }
  const detection: PortalDetection = {
    portal: result.portal,
    hostname: new URL(url).hostname,
    url,
    confidence: result.confidence,
    html_hash: htmlHash(url),
  };
  detectionByTab.set(tabId, detection);
  const badge = PORTAL_BADGES[result.portal];
  await setBadge(tabId, badge.text, badge.color);
}

async function setBadge(tabId: number, text: string, color: string): Promise<void> {
  try {
    await chrome.action.setBadgeText({ tabId, text });
    await chrome.action.setBadgeBackgroundColor({ tabId, color });
  } catch {
    /* tab gone */
  }
}

// ---------------------------------------------------------------------------
// API proxy with 401 refresh
// ---------------------------------------------------------------------------

const DEFAULT_API_BASE = "http://localhost:8000";

async function getApiBase(): Promise<string> {
  const v = await storageGetOptional<string>(STORAGE_KEYS.apiBase);
  if (typeof v === "string" && v.length > 0) return v.replace(/\/+$/, "");
  return DEFAULT_API_BASE;
}

function joinUrl(base: string, path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  return `${base}${path.startsWith("/") ? "" : "/"}${path}`;
}

let refreshInFlight: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;
  refreshInFlight = (async () => {
    try {
      const refresh = await storageGetOptional<string>(STORAGE_KEYS.refresh);
      if (!refresh) return false;
      const base = await getApiBase();
      const resp = await fetch(joinUrl(base, "/v1/auth/refresh"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({ refresh_token: refresh }),
        credentials: "omit",
      });
      if (!resp.ok) return false;
      const data = (await resp.json().catch(() => null)) as {
        access_token?: string;
        refresh_token?: string;
      } | null;
      if (!data || typeof data.access_token !== "string") return false;
      await storageSet(STORAGE_KEYS.access, data.access_token);
      if (typeof data.refresh_token === "string") {
        await storageSet(STORAGE_KEYS.refresh, data.refresh_token);
      }
      return true;
    } catch {
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

interface FetchResult {
  status: number;
  json: unknown;
}

async function fetchJson(
  method: string,
  path: string,
  body: unknown,
  headers: Record<string, string>,
): Promise<FetchResult> {
  const base = await getApiBase();
  const access = await storageGetOptional<string>(STORAGE_KEYS.access);

  const h: Record<string, string> = {
    Accept: "application/json",
    ...headers,
  };
  if (access) h["Authorization"] = `Bearer ${access}`;

  const init: RequestInit = { method, headers: h, credentials: "omit" };
  if (body !== undefined && method !== "GET") {
    h["Content-Type"] = h["Content-Type"] ?? "application/json";
    init.body = typeof body === "string" ? body : JSON.stringify(body);
  }

  const resp = await fetch(joinUrl(base, path), init);
  const text = await resp.text();
  let json: unknown = null;
  if (text.length > 0) {
    try {
      json = JSON.parse(text);
    } catch {
      json = { raw: text };
    }
  }
  return { status: resp.status, json };
}

async function apiCall(
  method: string,
  path: string,
  body: unknown,
  headers: Record<string, string>,
): Promise<FetchResult> {
  const first = await fetchJson(method, path, body, headers);
  if (first.status !== 401) return first;
  // Try refresh, retry once.
  const refreshed = await refreshAccessToken();
  if (!refreshed) return first;
  return fetchJson(method, path, body, headers);
}

// ---------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------

const handlers: HandlerMap = {
  "vault.unlock": async (_m) => {
    // Vault state lives in the popup process. Background only records the
    // unlock timestamp so it can drive the auto-lock alarm.
    await storageSet(STORAGE_KEYS.vaultUnlockedAt, Date.now());
    return { ok: true, unlocked: true };
  },
  "vault.lock": async () => {
    await storageRemove(STORAGE_KEYS.vaultUnlockedAt);
    return { ok: true };
  },
  "vault.status": async () => {
    const initialized = await storageGet<boolean>(STORAGE_KEYS.vaultInitialized, false);
    const unlockedAt = await storageGet<number | null>(STORAGE_KEYS.vaultUnlockedAt, null);
    const auto_lock_minutes = await getAutoLockMinutes();
    return {
      ok: true,
      initialized,
      unlocked: unlockedAt !== null,
      auto_lock_minutes,
    };
  },
  "vault.init": async () => {
    await storageSet(STORAGE_KEYS.vaultUnlockedAt, Date.now());
    return { ok: true, initialized: true };
  },
  "portal.detect": async (m, sender) => {
    // Allow content scripts to refine detection (e.g. with body-hash boost).
    // Key by sender.tab.id so subsequent "portal.active" lookups (which the
    // popup makes by tabId) actually hit the right entry. The previous
    // implementation keyed by `m.detection.url.length`, which silently
    // bucketed every detection into a colliding numeric key.
    const tabId = sender.tab?.id;
    if (tabId === undefined) {
      return { ok: true, stored: false };
    }
    detectionByTab.set(tabId, m.detection);
    return { ok: true, stored: true };
  },
  "portal.active": async (m) => {
    const detection = detectionByTab.get(m.tabId) ?? null;
    return { ok: true, detection };
  },
  "profile.active": async () => {
    // The vault is owned by the popup process — background never sees
    // decrypted profile material. Content scripts call this to discover
    // whether a profile is loaded; the popup performs the actual fill
    // because it holds the session key.
    return { ok: true, profile: null, locked: true };
  },
  "portal.fill": async (m) => {
    // The popup is responsible for the actual fill (it loads the
    // profile from the unlocked vault and sends a content.fill message
    // to the tab). Background just logs the request.
    await appendActivity({
      id: newActivityId(),
      ts: Date.now(),
      kind: "fill",
      portal: m.portal,
      supplier_id: m.supplierId,
      detail: `fill requested tab=${m.tabId}`,
    });
    return { ok: true, filled: 0, skipped: 0 };
  },
  "submission.capture": async (m) => {
    const pending = await queueSubmission(m.payload);
    await appendActivity({
      id: newActivityId(),
      ts: Date.now(),
      kind: "capture",
      portal: null,
      supplier_id: m.payload.supplier_id,
      detail: `captured submission queued id=${pending.id}`,
    });
    // Best-effort immediate drain.
    void drainPending();
    return { ok: true, id: pending.id };
  },
  "sync.now": async () => {
    const status = await syncNow();
    await appendActivity({
      id: newActivityId(),
      ts: Date.now(),
      kind: "sync",
      portal: null,
      supplier_id: null,
      detail: status.last_error
        ? `sync failed: ${status.last_error}`
        : `sync ok: ${status.supplier_count} suppliers / ${status.submission_count} submissions`,
    });
    return { ok: true, ...status };
  },
  "sync.status": async () => {
    const status: SyncStatus = await getSyncStatus();
    return { ok: true, ...status };
  },
  "api.call": async (m) => {
    try {
      const result = await apiCall(m.method, m.path, m.body, m.headers ?? {});
      if (result.status < 200 || result.status >= 300) {
        return {
          ok: false,
          error: `http_${result.status}`,
          status: result.status,
          json: result.json,
        };
      }
      return { ok: true, status: result.status, json: result.json };
    } catch (err) {
      return {
        ok: false,
        error: err instanceof Error ? err.message : "api_call_failed",
      };
    }
  },
  "auth.refresh": async () => {
    const refreshed = await refreshAccessToken();
    return { ok: true, refreshed };
  },
  "auth.connect": async (m) => {
    await storageSet(STORAGE_KEYS.apiBase, m.apiBase.replace(/\/+$/, ""));
    await storageSet(STORAGE_KEYS.access, m.accessToken);
    if (m.refreshToken) {
      await storageSet(STORAGE_KEYS.refresh, m.refreshToken);
    }
    // Validate via /v1/auth/me. If it fails, roll back tokens.
    const resp = await apiCall("GET", "/v1/auth/me", undefined, {});
    if (resp.status !== 200) {
      await storageRemove(STORAGE_KEYS.access);
      if (m.refreshToken) await storageRemove(STORAGE_KEYS.refresh);
      return {
        ok: false,
        error: `auth_failed:${resp.status}`,
      };
    }
    return { ok: true, user: resp.json as never };
  },
  "auth.me": async () => {
    const resp = await apiCall("GET", "/v1/auth/me", undefined, {});
    if (resp.status !== 200) {
      return { ok: false, error: `auth_me_failed:${resp.status}` };
    }
    return { ok: true, user: resp.json as never };
  },
  "auth.disconnect": async () => {
    await storageRemove(STORAGE_KEYS.access);
    await storageRemove(STORAGE_KEYS.refresh);
    await storageRemove(STORAGE_KEYS.vaultUnlockedAt);
    return { ok: true };
  },
  "activity.append": async (m) => {
    await appendActivity(m.entry);
    return { ok: true, id: m.entry.id };
  },
  "activity.list": async (m) => {
    const items = await listActivity(m.limit ?? 20);
    return { ok: true, items };
  },
  "badge.set": async (m) => {
    await setBadge(m.tabId, m.text, m.color);
    return { ok: true };
  },
};

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------

function bootstrap(): void {
  chrome.runtime.onInstalled.addListener(() => undefined);

  routeMessages(handlers);
  registerAlarms();

  chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    void onTabUpdated(tabId, changeInfo, tab);
  });

  chrome.tabs.onRemoved.addListener((tabId) => {
    detectionByTab.delete(tabId);
  });

  registerIdleAutoLock({
    lock: () => broadcastLock(),
    unlockedAt: () => storageGet<number | null>(STORAGE_KEYS.vaultUnlockedAt, null),
  });
}

bootstrap();

// ---------------------------------------------------------------------------
// Type re-exports (helpful for tests + downstream)
// ---------------------------------------------------------------------------

export type Platforms = PortalPlatform;

export const __test__ = {
  apiCall,
  fetchJson,
  refreshAccessToken,
  onTabUpdated,
  detectionByTab,
  handlers,
  ALARM_SYNC,
  ALARM_RETRY,
  ALARM_LOCK,
  maybeAutoLock,
  setBadge,
};
