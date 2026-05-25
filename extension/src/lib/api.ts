/**
 * Typed Once API client — proxies every HTTP request through the
 * background service worker via `chrome.runtime.sendMessage({type:
 * "api.call", ...})` so that all network egress is centralised, the JWT
 * is attached in one place, and the popup / content scripts never touch
 * `fetch` directly.
 *
 * Background contract (see `extension/src/background/index.ts` and
 * `extension/src/lib/messaging.ts` for the canonical discriminated union):
 *   request:  { type: "api.call", method, path, body?, headers? }
 *   response: { ok: boolean, status: number, json: unknown, error?: string }
 *
 * Token-save flow uses `auth.connect` (validates via /v1/auth/me and
 * rolls back on failure). The popup's apiBase is read from storage so
 * we don't accidentally overwrite a previously-configured base.
 */

import type { PortalPlatform } from "../types/portal";
import { STORAGE_KEYS, storageGet } from "./storage";

// ---------------------------------------------------------------------------
// Wire types — mirror backend pydantic schemas.
// ---------------------------------------------------------------------------

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
}

export interface UserMe {
  id: string;
  email: string;
  full_name: string | null;
  tenant_id: string;
  role: string;
}

export interface SupplierListItem {
  id: string;
  legal_name: string;
  dba_name: string | null;
  primary_email: string | null;
  created_at: string;
}

export type SubmissionStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "retrying"
  | "blocked"
  | "platform_unsupported";

export interface SubmissionListItem {
  id: string;
  supplier_id: string;
  portal_id: string;
  status: SubmissionStatus;
  attempt_count: number;
  last_error: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SubmissionRead extends SubmissionListItem {
  tenant_id: string;
  consent_record_id: string | null;
  payload_json: Record<string, unknown> | null;
  result_json: Record<string, unknown> | null;
  claimed_at: string | null;
  started_at: string | null;
}

export interface SubmissionCreatePayload {
  supplier_id: string;
  portal_id: string;
  consent_record_id: string;
  payload: Record<string, unknown>;
}

export interface ReceiptListItem {
  id: string;
  tenant_id: string;
  supplier_id: string;
  submission_id: string;
  portal_platform: PortalPlatform;
  submitted_at: string;
  payload_hash: string;
  tos_version_hash: string;
  consent_record_id: string | null;
  signing_key_id: string;
  signature_b64: string;
  public_payload_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  verify_url: string | null;
}

export interface ConsentRead {
  id: string;
  tenant_id: string;
  supplier_id: string;
  scope: string;
  portal_ids_json: string[];
  granted_at: string;
  granted_by_user_id: string | null;
  revoked_at: string | null;
  signed_text: string;
  signature_b64: string;
}

export interface ConsentList {
  items: ConsentRead[];
  total: number;
  limit: number;
  offset: number;
}

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;
  readonly code: string;

  constructor(message: string, status: number, body: unknown, code: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
    this.code = code;
  }
}

export class ApiTransportError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiTransportError";
  }
}

// ---------------------------------------------------------------------------
// Message envelopes (must stay in sync with background/index.ts)
// ---------------------------------------------------------------------------

interface ApiCallMessage {
  type: "api.call";
  method: HttpMethod;
  path: string;
  body?: unknown;
  headers?: Record<string, string>;
}

interface ApiCallResponse {
  ok: boolean;
  status?: number;
  json?: unknown;
  error?: string;
}

interface AuthConnectMessage {
  type: "auth.connect";
  apiBase: string;
  accessToken: string;
  refreshToken?: string;
}

interface AuthConnectResponse {
  ok: boolean;
  user?: unknown;
  error?: string;
}

// ---------------------------------------------------------------------------
// Transport
// ---------------------------------------------------------------------------

function sendMessage<TReq, TResp>(message: TReq): Promise<TResp> {
  if (typeof chrome === "undefined" || !chrome.runtime || !chrome.runtime.sendMessage) {
    return Promise.reject(new ApiTransportError("chrome.runtime.sendMessage is unavailable"));
  }
  return new Promise<TResp>((resolve, reject) => {
    try {
      chrome.runtime.sendMessage(message, (response: unknown) => {
        const lastError = chrome.runtime.lastError;
        if (lastError) {
          reject(new ApiTransportError(lastError.message ?? "chrome.runtime.sendMessage failed"));
          return;
        }
        resolve(response as TResp);
      });
    } catch (err) {
      reject(new ApiTransportError(err instanceof Error ? err.message : "sendMessage threw"));
    }
  });
}

function extractErrorCode(body: unknown, fallback: string): string {
  if (body && typeof body === "object") {
    const b = body as Record<string, unknown>;
    if (typeof b.detail === "string" && b.detail.length > 0) return b.detail;
    if (typeof b.code === "string" && b.code.length > 0) return b.code;
    if (typeof b.error === "string" && b.error.length > 0) return b.error;
  }
  return fallback;
}

async function call<T>(method: HttpMethod, path: string, body?: unknown, headers?: Record<string, string>): Promise<T> {
  const msg: ApiCallMessage = { type: "api.call", method, path };
  if (body !== undefined) msg.body = body;
  if (headers !== undefined) msg.headers = headers;

  const resp = await sendMessage<ApiCallMessage, ApiCallResponse>(msg);

  if (!resp || typeof resp !== "object") {
    throw new ApiTransportError("empty response from background");
  }
  if (!resp.ok) {
    const code = extractErrorCode(resp.json, resp.error ?? "http_error");
    throw new ApiError(`${method} ${path} failed: ${code}`, resp.status ?? 0, resp.json, code);
  }
  return resp.json as T;
}

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

export async function login(email: string, password: string): Promise<TokenPair> {
  const tokens = await call<TokenPair>("POST", "/v1/auth/login", {
    email,
    password,
  });
  // Persist via the canonical `auth.connect` handler. It re-validates the
  // freshly-issued access token against /v1/auth/me and rolls back on
  // failure, so we never leave a half-saved auth state in chrome.storage.
  const apiBase = await storageGet<string>(STORAGE_KEYS.apiBase, "");
  if (!apiBase) {
    throw new ApiTransportError("apiBase is not configured");
  }
  const save = await sendMessage<AuthConnectMessage, AuthConnectResponse>({
    type: "auth.connect",
    apiBase,
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
  });
  if (!save || !save.ok) {
    throw new ApiTransportError(save && save.error ? save.error : "failed to persist tokens");
  }
  return tokens;
}

export function me(): Promise<UserMe> {
  return call<UserMe>("GET", "/v1/auth/me");
}

export interface PortalListItem {
  id: string;
  platform: PortalPlatform;
  display_name: string;
  base_url: string | null;
  is_supported: boolean;
  risky: boolean;
}

export function listPortals(): Promise<PortalListItem[]> {
  return call<PortalListItem[]>("GET", "/v1/portals");
}

export function getSubmission(id: string): Promise<SubmissionRead> {
  return call<SubmissionRead>("GET", `/v1/submissions/${id}`);
}

export function listSuppliers(): Promise<SupplierListItem[]> {
  return call<SupplierListItem[]>("GET", "/v1/suppliers");
}

export function createSubmission(payload: SubmissionCreatePayload): Promise<SubmissionRead> {
  return call<SubmissionRead>("POST", "/v1/submissions", payload);
}

export function listSubmissions(): Promise<SubmissionListItem[]> {
  return call<SubmissionListItem[]>("GET", "/v1/submissions");
}

export function listReceipts(): Promise<ReceiptListItem[]> {
  return call<ReceiptListItem[]>("GET", "/v1/receipts");
}

export function getSubmissionReceipt(submissionId: string): Promise<ReceiptListItem> {
  return call<ReceiptListItem>("GET", `/v1/submissions/${submissionId}/receipt`);
}

export async function getConsentForPortal(supplierId: string, portalId: string): Promise<ConsentRead | null> {
  const params = new URLSearchParams({
    supplier_id: supplierId,
    portal_id: portalId,
    active: "true",
    limit: "1",
  });
  const list = await call<ConsentList>("GET", `/v1/consents?${params.toString()}`);
  return list.items[0] ?? null;
}

export const __test__ = {
  call,
  sendMessage,
  extractErrorCode,
};
