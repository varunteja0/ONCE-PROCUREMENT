import { api } from '@/services/api';
import type { PagedResponse } from '@/types/api';

/**
 * Build a typed CRUD client for a `/v1/{resource}` REST collection.
 * The backend convention (per L2.6) returns `{items, total, limit, offset}`
 * for list endpoints and the bare resource for create/get/update/delete.
 */
export interface CrudParams {
  supplier_id?: string | undefined;
  search?: string | undefined;
  limit?: number | undefined;
  offset?: number | undefined;
}

export interface CrudClient<T, TCreate> {
  list: (params?: CrudParams) => Promise<PagedResponse<T>>;
  get: (id: string) => Promise<T>;
  create: (input: TCreate) => Promise<T>;
  update: (id: string, patch: Partial<TCreate>) => Promise<T>;
  remove: (id: string) => Promise<void>;
}

export function createCrudClient<T, TCreate>(
  resourcePath: string,
): CrudClient<T, TCreate> {
  return {
    list: async (params: CrudParams = {}) => {
      const resp = await api.get<PagedResponse<T>>(`/${resourcePath}`, {
        params: {
          supplier_id: params.supplier_id,
          search: params.search,
          limit: params.limit ?? 50,
          offset: params.offset ?? 0,
        },
      });
      return resp.data;
    },
    get: async (id) => {
      const resp = await api.get<T>(`/${resourcePath}/${id}`);
      return resp.data;
    },
    create: async (input) => {
      const resp = await api.post<T>(`/${resourcePath}`, input);
      return resp.data;
    },
    update: async (id, patch) => {
      const resp = await api.patch<T>(`/${resourcePath}/${id}`, patch);
      return resp.data;
    },
    remove: async (id) => {
      await api.delete(`/${resourcePath}/${id}`);
    },
  };
}
