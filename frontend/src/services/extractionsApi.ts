// --- L3.8 pdf extraction ---
/**
 * Typed wrappers around `POST/GET /v1/extractions/*`.
 *
 * The extraction pipeline is a three-phase flow:
 *
 *   1. POST `/document` enqueues an extraction → returns the row with
 *      `status=pending`.
 *   2. The worker runs the regex+heuristic pipeline → status flips to
 *      `succeeded` / `partial` / `failed` with per-field confidences.
 *   3. The operator reviews and either POSTs `/accept` (with optional
 *      field overrides) or `/reject` (with an optional reason).
 *
 * All requests go through the shared authed `api` axios instance.
 */

import { api } from '@/services/api';

export type ExtractionSourceType = 'coi' | 'eo_certificate' | 'producer_license';

export type ExtractionStatus =
  | 'pending'
  | 'succeeded'
  | 'partial'
  | 'failed'
  | 'accepted'
  | 'rejected';

export interface ExtractionRead {
  id: string;
  tenant_id: string;
  source_document_type: ExtractionSourceType | string;
  source_document_id: string;
  raw_text_url: string | null;
  extracted_fields: Record<string, unknown> | null;
  field_confidences: Record<string, number> | null;
  warnings: string[] | null;
  extractor_version: string;
  status: ExtractionStatus | string;
  error: string | null;
  reviewed_by_user_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExtractionListResponse {
  items: ExtractionRead[];
  total: number;
  limit: number;
  offset: number;
}

export interface ExtractionEnqueueInput {
  document_type: ExtractionSourceType;
  document_id: string;
}

export interface ExtractionAcceptInput {
  id: string;
  fields?: Record<string, unknown>;
}

export interface ExtractionRejectInput {
  id: string;
  reason?: string;
}

export const extractionsApi = {
  async enqueue(input: ExtractionEnqueueInput): Promise<ExtractionRead> {
    const r = await api.post<ExtractionRead>('/extractions/document', input);
    return r.data;
  },

  async get(id: string): Promise<ExtractionRead> {
    const r = await api.get<ExtractionRead>(`/extractions/${id}`);
    return r.data;
  },

  async list(
    params: {
      document_type?: ExtractionSourceType;
      limit?: number;
      offset?: number;
    } = {},
  ): Promise<ExtractionListResponse> {
    const r = await api.get<ExtractionListResponse>('/extractions', { params });
    return r.data;
  },

  async accept(input: ExtractionAcceptInput): Promise<ExtractionRead> {
    const r = await api.post<ExtractionRead>(`/extractions/${input.id}/accept`, {
      fields: input.fields ?? {},
    });
    return r.data;
  },

  async reject(input: ExtractionRejectInput): Promise<ExtractionRead> {
    const r = await api.post<ExtractionRead>(`/extractions/${input.id}/reject`, {
      reason: input.reason ?? null,
    });
    return r.data;
  },
};

export default extractionsApi;
// --- /L3.8 pdf extraction ---
