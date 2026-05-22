import { api } from '@/services/api';
import type { ConsentRecord, PagedResponse } from '@/types/api';

export interface ConsentsListParams {
  supplier_id?: string;
  active_only?: boolean;
  limit?: number;
  offset?: number;
}

export const consentsApi = {
  list: async (
    params: ConsentsListParams = {},
  ): Promise<PagedResponse<ConsentRecord>> => {
    const resp = await api.get<PagedResponse<ConsentRecord>>('/consents', {
      params: {
        supplier_id: params.supplier_id,
        active_only: params.active_only,
        limit: params.limit ?? 100,
        offset: params.offset ?? 0,
      },
    });
    return resp.data;
  },
  get: async (id: string): Promise<ConsentRecord> => {
    const resp = await api.get<ConsentRecord>(`/consents/${id}`);
    return resp.data;
  },
};
