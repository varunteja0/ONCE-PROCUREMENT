import type { Portal, PortalListResponse } from "@/services/api";
import { api } from "@/services/api";
import { useQuery, type UseQueryResult } from "@tanstack/react-query";

export interface UsePortalsParams {
  supportedOnly?: boolean;
  search?: string;
  page?: number;
  pageSize?: number;
}

const DEFAULT_PAGE_SIZE = 100;

export const portalsKeys = {
  all: ["portals"] as const,
  list: (params: UsePortalsParams) => ["portals", "list", params] as const,
  detail: (id: string) => ["portals", "detail", id] as const,
};

export function usePortals(params: UsePortalsParams = {}): UseQueryResult<PortalListResponse, Error> {
  const page = params.page ?? 1;
  const pageSize = params.pageSize ?? DEFAULT_PAGE_SIZE;
  return useQuery({
    queryKey: portalsKeys.list({ ...params, page, pageSize }),
    queryFn: async () => {
      const resp = await api.get<PortalListResponse>("/portals", {
        params: {
          is_supported: params.supportedOnly,
          search: params.search,
          limit: pageSize,
          offset: (page - 1) * pageSize,
        },
      });
      return resp.data;
    },
  });
}

export function usePortal(portalId: string | undefined): UseQueryResult<Portal, Error> {
  return useQuery({
    queryKey: portalId ? portalsKeys.detail(portalId) : ["portals", "detail", "noop"],
    enabled: Boolean(portalId),
    queryFn: async () => {
      const resp = await api.get<Portal>(`/portals/${portalId}`);
      return resp.data;
    },
  });
}
