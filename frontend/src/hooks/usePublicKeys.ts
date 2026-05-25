import { api } from "@/services/api";
import { useQuery, type UseQueryResult } from "@tanstack/react-query";

export interface PublicKeyRow {
  key_id: string;
  algorithm: string;
  public_key_pem: string;
  created_at: string;
  revoked_at: string | null;
  status: "active" | "revoked";
  description: string | null;
}

export interface PublicKeysResponse {
  keys: PublicKeyRow[];
  count: number;
}

export const publicKeysKeys = {
  all: ["public-keys"] as const,
  list: (includeRevoked: boolean) => ["public-keys", "list", includeRevoked] as const,
};

export function usePublicKeys(includeRevoked: boolean = true): UseQueryResult<PublicKeysResponse, Error> {
  return useQuery({
    queryKey: publicKeysKeys.list(includeRevoked),
    queryFn: async () => {
      const resp = await api.get<PublicKeysResponse>("/public/keys", {
        params: { include_revoked: includeRevoked },
      });
      return resp.data;
    },
    staleTime: 5 * 60_000,
  });
}
