// --- L3.10 audit ---
/**
 * Typed wrappers around `GET/POST /v1/audit/*`.
 *
 * Backed by the tamper-evident `audit_trail` chain. Every mutating
 * request emits exactly one row (best-effort, fire-and-forget on the
 * server) with a SHA-256 chain hash linking it to the prior row. The
 * `/audit/chain/verify` endpoint replays the chain and is the source
 * of truth for the verification badge on every page.
 */

import { api } from '@/services/api';

export type AuditActorType =
  | 'user'
  | 'operator'
  | 'system'
  | 'inbound_email'
  | 'webhook'
  | 'worker';

export type AuditExportScope =
  | 'tenant'
  | 'supplier'
  | 'submission'
  | 'date_range';

export type AuditExportStatus =
  | 'pending'
  | 'generating'
  | 'ready'
  | 'failed';

export interface AuditLogRead {
  id: string;
  tenant_id: string;
  chain_position: number;
  prev_hash: string;
  this_hash: string;
  occurred_at: string;
  actor_type: AuditActorType;
  actor_id: string | null;
  actor_email: string | null;
  action_verb: string;
  resource_type: string;
  resource_id: string | null;
  resource_label: string | null;
  request_id: string | null;
  ip: string | null;
  user_agent: string | null;
  payload_summary: Record<string, unknown> | null;
  signature_key_id: string | null;
}

export interface AuditLogList {
  items: AuditLogRead[];
  total: number;
  limit: number;
  offset: number;
}

export interface AuditChainBreak {
  chain_position: number;
  row_id: string;
  expected_prev_hash: string;
  actual_prev_hash: string;
  expected_this_hash: string;
  actual_this_hash: string;
  reason: 'prev_hash_mismatch' | 'this_hash_mismatch' | 'position_gap';
}

export interface AuditChainVerifyResult {
  tenant_id: string;
  valid: boolean;
  rows_checked: number;
  from_position: number;
  to_position: number;
  breaks: AuditChainBreak[];
}

export interface AuditExportCreate {
  scope: AuditExportScope;
  scope_params?: Record<string, unknown>;
}

export interface AuditExportRead {
  id: string;
  tenant_id: string;
  scope_type: AuditExportScope;
  scope_params: Record<string, unknown> | null;
  requested_by_user_id: string | null;
  status: AuditExportStatus;
  row_count: number | null;
  file_path: string | null;
  file_sha256: string | null;
  signed_envelope_path: string | null;
  envelope_sha256: string | null;
  requested_at: string;
  completed_at: string | null;
  expires_at: string | null;
  error: string | null;
}

export interface AuditExportListItem {
  id: string;
  scope_type: AuditExportScope;
  scope_params: Record<string, unknown> | null;
  status: AuditExportStatus;
  requested_at: string;
  completed_at: string | null;
  row_count: number | null;
  expires_at: string | null;
  error: string | null;
}

export interface AuditListParams {
  limit?: number;
  offset?: number;
  actor_type?: AuditActorType;
  action?: string;
  resource_type?: string;
  from?: string;
  to?: string;
  q?: string;
}

export const auditApi = {
  list(params: AuditListParams = {}) {
    return api.get<AuditLogList>('/audit', { params }).then((r) => r.data);
  },
  get(id: string) {
    return api.get<AuditLogRead>(`/audit/${id}`).then((r) => r.data);
  },
  byResource(resourceType: string, resourceId: string) {
    return api
      .get<AuditLogList>(`/audit/by-resource/${resourceType}/${resourceId}`)
      .then((r) => r.data);
  },
  verify(params: { from_position?: number; to_position?: number } = {}) {
    return api
      .get<AuditChainVerifyResult>('/audit/chain/verify', { params })
      .then((r) => r.data);
  },
  listExports() {
    return api
      .get<AuditExportListItem[]>('/audit/exports')
      .then((r) => r.data);
  },
  getExport(id: string) {
    return api
      .get<AuditExportRead>(`/audit/exports/${id}`)
      .then((r) => r.data);
  },
  createExport(body: AuditExportCreate) {
    return api
      .post<AuditExportRead>('/audit/exports', body)
      .then((r) => r.data);
  },
  downloadExportUrl(id: string) {
    return `/v1/audit/exports/${id}/download`;
  },
  downloadEnvelopeUrl(id: string) {
    return `/v1/audit/exports/${id}/download/envelope`;
  },
};
