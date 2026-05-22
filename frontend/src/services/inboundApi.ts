// --- L3.9 inbound ---
/**
 * Typed wrappers around `GET/POST/PATCH/DELETE /v1/inbound/*`.
 *
 * Inbound emails arrive via the Postmark webhook (or IMAP poll) and are
 * persisted as `InboundEmail` rows with `InboundAttachment` siblings.
 * Each email runs through tenant-scoped routing rules and (by default)
 * produces a draft `Submission`.
 */

import { api } from '@/services/api';

export type InboundStatus =
  | 'received'
  | 'parsing'
  | 'routed'
  | 'quarantined'
  | 'routing_failed'
  | 'discarded';

export type InboundAction =
  | 'create_submission'
  | 'quarantine'
  | 'discard'
  | 'tag_only';

export interface InboundAttachment {
  id: string;
  filename: string;
  content_type: string | null;
  size_bytes: number;
  sha256: string;
  storage_url: string;
  scanned_at: string | null;
}

export interface InboundEmailListItem {
  id: string;
  tenant_id: string;
  message_id: string;
  from_address: string;
  from_name: string | null;
  to_address: string;
  subject: string | null;
  received_at: string;
  status: InboundStatus;
  spam_score: number | null;
  routing_error: string | null;
  attachment_count: number;
  draft_submission_id: string | null;
  draft_supplier_id: string | null;
}

export interface InboundEmailDetail extends InboundEmailListItem {
  in_reply_to: string | null;
  cc_addresses: string[] | null;
  raw_body_text: string | null;
  raw_body_html: string | null;
  headers: Record<string, unknown> | null;
  raw_storage_url: string | null;
  attachments: InboundAttachment[];
}

export interface InboundRule {
  id: string;
  tenant_id: string;
  name: string;
  priority: number;
  match_from_domain: string | null;
  match_subject_regex: string | null;
  match_attachment_kind: string | null;
  action: InboundAction;
  action_params: Record<string, unknown> | null;
  active: boolean;
  created_at: string;
}

export interface InboundRuleCreate {
  name: string;
  priority?: number;
  match_from_domain?: string | null;
  match_subject_regex?: string | null;
  match_attachment_kind?: string | null;
  action?: InboundAction;
  action_params?: Record<string, unknown> | null;
  active?: boolean;
}

export type InboundRuleUpdate = Partial<InboundRuleCreate>;

export interface InboundRetryResponse {
  id: string;
  status: InboundStatus;
  routing_error: string | null;
}

export const inboundApi = {
  list(params: { limit?: number; offset?: number; status?: InboundStatus } = {}) {
    return api
      .get<InboundEmailListItem[]>('/inbound', { params })
      .then((r) => r.data);
  },
  get(id: string) {
    return api.get<InboundEmailDetail>(`/inbound/${id}`).then((r) => r.data);
  },
  retry(id: string) {
    return api
      .post<InboundRetryResponse>(`/inbound/${id}/retry`)
      .then((r) => r.data);
  },
  quarantine(id: string) {
    return api
      .post<InboundRetryResponse>(`/inbound/${id}/quarantine`)
      .then((r) => r.data);
  },
  listRules() {
    return api.get<InboundRule[]>('/inbound/rules').then((r) => r.data);
  },
  createRule(body: InboundRuleCreate) {
    return api.post<InboundRule>('/inbound/rules', body).then((r) => r.data);
  },
  updateRule(id: string, body: InboundRuleUpdate) {
    return api
      .patch<InboundRule>(`/inbound/rules/${id}`, body)
      .then((r) => r.data);
  },
  deleteRule(id: string) {
    return api.delete(`/inbound/rules/${id}`).then(() => undefined);
  },
  reorderRules(order: string[]) {
    return api
      .post<InboundRule[]>('/inbound/rules/reorder', { order })
      .then((r) => r.data);
  },
};
