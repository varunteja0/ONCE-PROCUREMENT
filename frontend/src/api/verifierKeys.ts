/**
 * Verifier API key admin endpoints (Phase L6.1 monetization).
 *
 * Wraps the tenant-scoped admin surface at `/v1/admin/verifier-keys`. The
 * `plaintext` field returned by `issueVerifierKey` is shown to the user
 * ONCE and is never re-fetchable \u2014 callers must surface it immediately
 * in the UI.
 */

import { api } from '@/services/api';

export interface VerifierKey {
  id: string;
  tenant_id: string;
  name: string;
  key_prefix: string;
  monthly_call_cap: number | null;
  last_used_at: string | null;
  created_at: string;
  revoked_at: string | null;
}

export interface VerifierKeyIssued extends VerifierKey {
  /** Shown ONCE. Never re-fetchable. */
  plaintext: string;
}

export interface VerifierKeyCreateInput {
  name: string;
  /**
   * Monthly call cap.
   * - `null` / omitted \u2192 free-tier default (server-side).
   * - `0` \u2192 uncapped (paid metered tier).
   * - `> 0` \u2192 hard cap.
   */
  monthly_call_cap?: number | null;
}

export interface VerifierKeyListResponse {
  keys: VerifierKey[];
}

export async function listVerifierKeys(): Promise<VerifierKey[]> {
  const resp = await api.get<VerifierKeyListResponse>('/admin/verifier-keys');
  return resp.data.keys;
}

export async function issueVerifierKey(
  input: VerifierKeyCreateInput,
): Promise<VerifierKeyIssued> {
  const resp = await api.post<VerifierKeyIssued>(
    '/admin/verifier-keys',
    input,
  );
  return resp.data;
}

export async function revokeVerifierKey(id: string): Promise<void> {
  await api.delete(`/admin/verifier-keys/${id}`);
}
