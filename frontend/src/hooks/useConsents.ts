import { consentsApi, type ConsentsListParams } from "@/api/consents";
import type { ConsentRecord, PagedResponse } from "@/types/api";
import { useQuery, type UseQueryResult } from "@tanstack/react-query";

export const consentsKeys = {
  all: ["consents"] as const,
  list: (params: ConsentsListParams) => ["consents", "list", params] as const,
  detail: (id: string) => ["consents", "detail", id] as const,
};

export function useConsents(
  params: ConsentsListParams = {},
  options: { enabled?: boolean } = {},
): UseQueryResult<PagedResponse<ConsentRecord>, Error> {
  return useQuery({
    queryKey: consentsKeys.list(params),
    queryFn: () => consentsApi.list(params),
    enabled: options.enabled ?? true,
  });
}

export function useConsent(id: string | undefined): UseQueryResult<ConsentRecord, Error> {
  return useQuery({
    queryKey: id ? consentsKeys.detail(id) : ["consents", "detail", "noop"],
    enabled: Boolean(id),
    queryFn: () => consentsApi.get(id ?? ""),
  });
}
