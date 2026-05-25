import { apiAuth } from "@/api/auth";
import { logger } from "@/lib/logger";
import { register as registerService } from "@/services/auth";
import { useAuthStore } from "@/store/auth";
import type { LoginInput, RegisterInput, UserMe } from "@/types/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";

export const authKeys = {
  me: ["auth", "me"] as const,
};

export interface UseAuthResult {
  user: UserMe | null;
  tenantId: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (input: LoginInput) => Promise<UserMe>;
  /** @deprecated Use the dedicated register flow; kept for back-compat. */
  register: (input: RegisterInput) => Promise<UserMe>;
  logout: () => void;
  refreshMe: () => Promise<UserMe>;
}

export function useAuth(): UseAuthResult {
  const storeUser = useAuthStore((s) => s.user);
  const storeTenantId = useAuthStore((s) => s.tenantId);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const setSession = useAuthStore((s) => s.setSession);
  const setUser = useAuthStore((s) => s.setUser);
  const clearSession = useAuthStore((s) => s.clearSession);
  const queryClient = useQueryClient();

  // Server-state for the authenticated user. The Zustand store remains
  // populated (for legacy consumers / route guards) but TanStack Query is
  // the authoritative source going forward.
  const meQuery = useQuery<UserMe, Error>({
    queryKey: authKeys.me,
    queryFn: async () => {
      const profile = await apiAuth.me();
      // Mirror into the legacy store so out-of-boundary callers
      // (ProtectedRoute, IdleGuard) continue to see fresh values.
      setUser(profile);
      return profile;
    },
    enabled: isAuthenticated,
    staleTime: 60_000,
  });

  const user: UserMe | null = meQuery.data ?? storeUser;
  const tenantId: string | null = user?.tenant_id ?? storeTenantId;

  const completeLogin = useCallback(async (): Promise<UserMe> => {
    const profile = await apiAuth.me();
    setSession(profile);
    await queryClient.invalidateQueries({ queryKey: authKeys.me });
    return profile;
  }, [setSession, queryClient]);

  const login = useCallback(
    async (input: LoginInput): Promise<UserMe> => {
      await apiAuth.login(input);
      return completeLogin();
    },
    [completeLogin],
  );

  const register = useCallback(
    async (input: RegisterInput): Promise<UserMe> => {
      // `registerService` returns a TokenPair just like login.
      await registerService(input);
      return completeLogin();
    },
    [completeLogin],
  );

  const logout = useCallback((): void => {
    try {
      apiAuth.logout();
    } catch (err) {
      logger.captureException(err, { where: "useAuth.logout" });
    }
    clearSession();
    queryClient.clear();
  }, [clearSession, queryClient]);

  const refreshMe = useCallback(async (): Promise<UserMe> => {
    const profile = await apiAuth.me();
    setUser(profile);
    queryClient.setQueryData(authKeys.me, profile);
    return profile;
  }, [setUser, queryClient]);

  return {
    user,
    tenantId,
    isAuthenticated,
    isLoading: meQuery.isLoading,
    login,
    register,
    logout,
    refreshMe,
  };
}
