import { api } from "@/services/api";
import { useQuery, type UseQueryResult } from "@tanstack/react-query";

export type PortalHealthStatus = "healthy" | "degraded" | "down" | "unknown";

export interface PublicPortalRow {
  platform: string;
  display_name: string;
  supported: boolean;
  status: PortalHealthStatus;
  last_status_change_at: string | null;
  consecutive_failures: number;
}

export interface PublicPortalsResponse {
  portals: PublicPortalRow[];
  supported_count: number;
  healthy_count: number;
  total_count: number;
}

export const publicPortalsKeys = {
  all: ["public-portals"] as const,
  list: () => ["public-portals", "list"] as const,
};

export function usePublicPortals(): UseQueryResult<PublicPortalsResponse, Error> {
  return useQuery({
    queryKey: publicPortalsKeys.list(),
    queryFn: async () => {
      const resp = await api.get<PublicPortalsResponse>("/public/portals");
      return resp.data;
    },
    staleTime: 60_000,
  });
}
