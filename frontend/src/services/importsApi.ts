// --- L3.7 imports ---
/**
 * Typed wrappers around `POST/GET /v1/imports/*`.
 *
 * The bulk-import pipeline is a two-phase flow:
 *
 *   1. Upload a CSV/XLSX -> server runs dry-run validation -> returns the
 *      `ImportJob` with `status=dry_run_ready` (or `failed`) plus row counts.
 *   2. Operator reviews errors/preview -> POSTs `/commit { confirmed: true }`
 *      -> server flips the job to `importing` and inserts in chunks.
 *
 * All requests go through the shared authed `api` axios instance.
 */

import { api } from '@/services/api';

export type ImportEntityType =
  | 'supplier'
  | 'coi'
  | 'loss_run'
  | 'producer_license';

export type ImportStatus =
  | 'pending'
  | 'validating'
  | 'dry_run_ready'
  | 'importing'
  | 'completed'
  | 'failed'
  | 'canceled';

export type OnDuplicateMode = 'error' | 'update' | 'skip';

export interface ImportRowError {
  row_number: number;
  column: string | null;
  value: string | null;
  error_code: string;
  error_message: string;
}

export interface ImportJob {
  id: string;
  tenant_id: string;
  entity_type: ImportEntityType;
  status: ImportStatus;
  original_filename: string;
  file_size_bytes: number;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  imported_rows: number;
  on_duplicate: OnDuplicateMode;
  mapping: Record<string, string> | null;
  summary: Record<string, unknown> | null;
  last_error: string | null;
  created_by_user_id: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface ImportJobListItem {
  id: string;
  entity_type: ImportEntityType;
  status: ImportStatus;
  original_filename: string;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  imported_rows: number;
  created_at: string;
  completed_at: string | null;
}

export interface ImportJobDetail extends ImportJob {
  errors_preview: ImportRowError[];
  error_count: number;
}

export interface ImportColumnSpec {
  field: string;
  required: boolean;
  aliases: string[];
  description: string;
  example: string | null;
}

export interface ImportColumnsResponse {
  entity_type: ImportEntityType;
  columns: ImportColumnSpec[];
}

export interface ImportUploadInput {
  file: File;
  entity_type: ImportEntityType;
  mapping?: Record<string, string>;
  on_duplicate?: OnDuplicateMode;
}

/** Convert FormData on upload — `mapping` is sent as a JSON-encoded string. */
function buildUploadForm(input: ImportUploadInput): FormData {
  const fd = new FormData();
  fd.append('file', input.file, input.file.name);
  fd.append('entity_type', input.entity_type);
  if (input.mapping && Object.keys(input.mapping).length > 0) {
    fd.append('mapping', JSON.stringify(input.mapping));
  }
  fd.append('on_duplicate', input.on_duplicate ?? 'error');
  return fd;
}

export const importsApi = {
  async upload(input: ImportUploadInput): Promise<ImportJob> {
    const r = await api.post<ImportJob>('/imports', buildUploadForm(input), {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return r.data;
  },

  async list(params: { limit?: number; offset?: number } = {}): Promise<{
    items: ImportJobListItem[];
    total: number;
  }> {
    const r = await api.get<ImportJobListItem[]>('/imports', { params });
    const total = Number(r.headers['x-total-count'] ?? r.data.length);
    return { items: r.data, total };
  },

  async get(id: string): Promise<ImportJobDetail> {
    const r = await api.get<ImportJobDetail>(`/imports/${id}`);
    return r.data;
  },

  async commit(id: string): Promise<ImportJob> {
    const r = await api.post<ImportJob>(`/imports/${id}/commit`, {
      confirmed: true,
    });
    return r.data;
  },

  async cancel(id: string): Promise<ImportJob> {
    const r = await api.post<ImportJob>(`/imports/${id}/cancel`);
    return r.data;
  },

  async columns(entity: ImportEntityType): Promise<ImportColumnsResponse> {
    const r = await api.get<ImportColumnsResponse>(`/imports/columns/${entity}`);
    return r.data;
  },

  /** Returns a relative URL the browser can navigate to to download the CSV. */
  templateUrl(entity: ImportEntityType): string {
    const base =
      typeof import.meta.env.VITE_API_BASE === 'string' &&
      (import.meta.env.VITE_API_BASE as string).length > 0
        ? (import.meta.env.VITE_API_BASE as string)
        : '/v1';
    return `${base.replace(/\/$/, '')}/imports/template/${entity}`;
  },

  errorsUrl(id: string): string {
    const base =
      typeof import.meta.env.VITE_API_BASE === 'string' &&
      (import.meta.env.VITE_API_BASE as string).length > 0
        ? (import.meta.env.VITE_API_BASE as string)
        : '/v1';
    return `${base.replace(/\/$/, '')}/imports/${id}/errors.csv`;
  },
};

export default importsApi;
// --- /L3.7 imports ---
