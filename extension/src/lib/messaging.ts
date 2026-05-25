/**
 * Typed runtime-message bus for the Once extension.
 *
 * Design
 * ------
 * Every cross-context call (popup ↔ background, content ↔ background,
 * options ↔ background) goes through a single discriminated union of
 * `Message`s with a matching `Response<M>` mapping. The `send<M>(m)`
 * helper preserves the type relationship so callers get exhaustive
 * typing without `any` or runtime casts at the call site.
 *
 * The bus is strictly request/response — for "fire and forget" use the
 * `notify` helper which awaits but discards the result.
 *
 * We also expose `routeMessages(handlers)` for the background side; it
 * wires `chrome.runtime.onMessage` into a typed handler map and returns
 * `true` from the listener whenever the matching handler is async (which
 * is the MV3 contract for keeping the message channel open).
 */

import type { PortalPlatform } from "../types/portal";
import type { SupplierProfile } from "../types/profile";
import type { HttpMethod, SubmissionCreatePayload, SubmissionListItem, SupplierListItem, UserMe } from "./api";

// ---------------------------------------------------------------------------
// Common substructures
// ---------------------------------------------------------------------------

export interface PortalDetection {
  portal: PortalPlatform;
  hostname: string;
  url: string;
  /** 0..1 — combines URL pattern match + body hash heuristics. */
  confidence: number;
  /** Cheap content hash used to debounce repeated detections. */
  html_hash: string;
}

export interface ActivityEntry {
  id: string;
  ts: number;
  kind: "fill" | "capture" | "sync" | "unlock" | "lock" | "error";
  portal: PortalPlatform | null;
  supplier_id: string | null;
  detail: string;
}

export interface SyncStatus {
  last_sync_at: number | null;
  in_flight: boolean;
  last_error: string | null;
  supplier_count: number;
  submission_count: number;
}

export interface VaultStatusPayload {
  initialized: boolean;
  unlocked: boolean;
  auto_lock_minutes: number;
}

// ---------------------------------------------------------------------------
// Message envelope — discriminated union
// ---------------------------------------------------------------------------

export type Message =
  // vault
  | { type: "vault.unlock" }
  | { type: "vault.lock" }
  | { type: "vault.status" }
  | { type: "vault.init" }
  // portal detection / fill
  | { type: "portal.detect"; detection: PortalDetection }
  | { type: "portal.active"; tabId: number }
  | {
      type: "portal.fill";
      tabId: number;
      supplierId: string;
      portal: PortalPlatform;
      profile: SupplierProfile;
    }
  // submission capture / sync
  | { type: "submission.capture"; payload: SubmissionCreatePayload }
  | { type: "sync.now" }
  | { type: "sync.status" }
  // api proxy
  | {
      type: "api.call";
      method: HttpMethod;
      path: string;
      body?: unknown;
      headers?: Record<string, string>;
    }
  | { type: "auth.refresh" }
  | { type: "auth.connect"; apiBase: string; accessToken: string; refreshToken?: string }
  | { type: "auth.me" }
  | { type: "auth.disconnect" }
  // activity
  | { type: "activity.append"; entry: ActivityEntry }
  | { type: "activity.list"; limit?: number }
  // badge (background → tabs internal; exposed for tests)
  | { type: "badge.set"; tabId: number; text: string; color: string }
  // content-side message popup→content
  | { type: "content.fill"; profile: SupplierProfile; portal: PortalPlatform }
  // active vault profile probe (used by content dispatcher)
  | { type: "profile.active" };

// ---------------------------------------------------------------------------
// Response shape — must match each message type
// ---------------------------------------------------------------------------

export type Ok<T> = { ok: true } & T;
export type Err = { ok: false; error: string; code?: string; status?: number; json?: unknown };
export type Result<T> = Ok<T> | Err;

export interface ApiCallResult {
  status: number;
  json: unknown;
}

export interface ResponseMap {
  "vault.unlock": Result<{ unlocked: true }>;
  "vault.lock": { ok: true } | Err;
  "vault.status": Result<VaultStatusPayload>;
  "vault.init": Result<{ initialized: true }>;
  "portal.detect": Result<{ stored: boolean }>;
  "portal.active": Result<{ detection: PortalDetection | null }>;
  "portal.fill": Result<{ filled: number; skipped: number }>;
  "submission.capture": Result<{ id: string }>;
  "sync.now": Result<SyncStatus>;
  "sync.status": Result<SyncStatus>;
  "api.call": Result<ApiCallResult>;
  "auth.refresh": Result<{ refreshed: boolean }>;
  "auth.connect": Result<{ user: UserMe }>;
  "auth.me": Result<{ user: UserMe }>;
  "auth.disconnect": { ok: true } | Err;
  "activity.append": Result<{ id: string }>;
  "activity.list": Result<{ items: ActivityEntry[] }>;
  "badge.set": { ok: true } | Err;
  "content.fill": Result<{ filled: number; skipped: number }>;
  "profile.active": Result<{ profile: SupplierProfile | null; locked: boolean }>;
}

export type Response<M extends Message> = ResponseMap[M["type"]];

// Re-exports for downstream consumers (avoid pulling extra modules).
export type { HttpMethod, SubmissionCreatePayload, SubmissionListItem, SupplierListItem, UserMe };

// ---------------------------------------------------------------------------
// chrome.* wrappers (Promise-uniform)
// ---------------------------------------------------------------------------

export class MessagingTransportError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "MessagingTransportError";
  }
}

function hasRuntime(): boolean {
  return typeof chrome !== "undefined" && !!chrome.runtime && typeof chrome.runtime.sendMessage === "function";
}

/**
 * Type-preserving runtime sendMessage. Resolves with the matching
 * `Response<M>` or rejects with a `MessagingTransportError` if the
 * transport itself fails (extension reloaded, no listener registered).
 */
export function send<M extends Message>(message: M): Promise<Response<M>> {
  if (!hasRuntime()) {
    return Promise.reject(new MessagingTransportError("chrome.runtime is unavailable"));
  }
  return new Promise((resolve, reject) => {
    try {
      chrome.runtime.sendMessage(message, (response: unknown) => {
        const lastError = chrome.runtime.lastError;
        if (lastError) {
          reject(new MessagingTransportError(lastError.message ?? "sendMessage failed"));
          return;
        }
        if (response === undefined) {
          // Background returned nothing — treat as transport error so
          // call sites can distinguish from `{ok:false}` business errors.
          reject(new MessagingTransportError("empty response"));
          return;
        }
        resolve(response as Response<M>);
      });
    } catch (err) {
      reject(new MessagingTransportError(err instanceof Error ? err.message : "sendMessage threw"));
    }
  });
}

/**
 * Like `send` but resolves on success and throws an `Error` constructed
 * from `Err.error` on business failure. Useful when call sites want a
 * single try/catch rather than a discriminated check.
 */
export async function sendOrThrow<M extends Message>(message: M): Promise<Response<M> & { ok: true }> {
  const resp = await send(message);
  if (!resp.ok) {
    const e = new Error(resp.error);
    e.name = "MessagingError";
    throw e;
  }
  return resp as unknown as Response<M> & { ok: true };
}

/**
 * Fire-and-forget: send a message and swallow transport errors. Used in
 * content-script context where the popup may have closed before we
 * deliver a status update.
 */
export async function notify<M extends Message>(message: M): Promise<void> {
  try {
    await send(message);
  } catch {
    /* intentional */
  }
}

// ---------------------------------------------------------------------------
// Tab messaging (popup → content)
// ---------------------------------------------------------------------------

export function sendToTab<M extends Message>(tabId: number, message: M): Promise<Response<M>> {
  if (typeof chrome === "undefined" || !chrome.tabs || typeof chrome.tabs.sendMessage !== "function") {
    return Promise.reject(new MessagingTransportError("chrome.tabs.sendMessage is unavailable"));
  }
  return new Promise((resolve, reject) => {
    try {
      chrome.tabs.sendMessage(tabId, message, (response: unknown) => {
        const lastError = chrome.runtime?.lastError;
        if (lastError) {
          reject(new MessagingTransportError(lastError.message ?? "tabs.sendMessage failed"));
          return;
        }
        if (response === undefined) {
          reject(new MessagingTransportError("empty tab response"));
          return;
        }
        resolve(response as Response<M>);
      });
    } catch (err) {
      reject(new MessagingTransportError(err instanceof Error ? err.message : "tabs.sendMessage threw"));
    }
  });
}

// ---------------------------------------------------------------------------
// Background-side router
// ---------------------------------------------------------------------------

export type Handler<M extends Message> = (message: M, sender: chrome.runtime.MessageSender) => Promise<Response<M>>;

export type HandlerMap = {
  [K in Message["type"]]?: Handler<Extract<Message, { type: K }>>;
};

function isMessage(value: unknown): value is Message {
  if (!value || typeof value !== "object") return false;
  const t = (value as { type?: unknown }).type;
  return typeof t === "string" && t.length > 0;
}

/**
 * Wire `chrome.runtime.onMessage` to a typed handler map. Returns the
 * registered listener so tests / hot-reload can detach it.
 */
export function routeMessages(
  handlers: HandlerMap,
): (message: unknown, sender: chrome.runtime.MessageSender, sendResponse: (response: unknown) => void) => boolean {
  const listener = (
    message: unknown,
    sender: chrome.runtime.MessageSender,
    sendResponse: (response: unknown) => void,
  ): boolean => {
    if (!isMessage(message)) {
      sendResponse({ ok: false, error: "invalid_message" } satisfies Err);
      return false;
    }
    const type = message.type as Message["type"];
    const handler = handlers[type] as Handler<Extract<Message, { type: typeof type }>> | undefined;
    if (!handler) {
      sendResponse({
        ok: false,
        error: `no_handler:${type}`,
      } satisfies Err);
      return false;
    }
    handler(message as Extract<Message, { type: typeof type }>, sender)
      .then((resp) => sendResponse(resp))
      .catch((err: unknown) =>
        sendResponse({
          ok: false,
          error: err instanceof Error ? err.message : "handler_threw",
        } satisfies Err),
      );
    return true; // keep channel open for async
  };
  if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.onMessage) {
    chrome.runtime.onMessage.addListener(listener);
  }
  return listener;
}

export const __test__ = {
  isMessage,
};
