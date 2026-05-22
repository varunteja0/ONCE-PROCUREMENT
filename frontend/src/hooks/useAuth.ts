import { useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  login as loginService,
  logout as logoutService,
  me as meService,
  register as registerService,
} from '@/services/auth';
import { useAuthStore } from '@/store/auth';
import type {
  LoginInput,
  RegisterInput,
  TokenPair,
  UserMe,
} from '@/services/api';

export interface UseAuthResult {
  user: UserMe | null;
  tenantId: string | null;
  isAuthenticated: boolean;
  login: (input: LoginInput) => Promise<UserMe>;
  register: (input: RegisterInput) => Promise<UserMe>;
  logout: () => void;
  refreshMe: () => Promise<UserMe>;
}

export function useAuth(): UseAuthResult {
  const user = useAuthStore((s) => s.user);
  const tenantId = useAuthStore((s) => s.tenantId);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const setSession = useAuthStore((s) => s.setSession);
  const setUser = useAuthStore((s) => s.setUser);
  const clearSession = useAuthStore((s) => s.clearSession);
  const queryClient = useQueryClient();

  const completeLogin = useCallback(
    async (tokens: TokenPair): Promise<UserMe> => {
      const profile = await meService();
      setSession(profile, tokens);
      return profile;
    },
    [setSession],
  );

  const login = useCallback(
    async (input: LoginInput): Promise<UserMe> => {
      const tokens = await loginService(input);
      return completeLogin(tokens);
    },
    [completeLogin],
  );

  const register = useCallback(
    async (input: RegisterInput): Promise<UserMe> => {
      const tokens = await registerService(input);
      return completeLogin(tokens);
    },
    [completeLogin],
  );

  const logout = useCallback((): void => {
    logoutService();
    clearSession();
    queryClient.clear();
  }, [clearSession, queryClient]);

  const refreshMe = useCallback(async (): Promise<UserMe> => {
    const profile = await meService();
    setUser(profile);
    return profile;
  }, [setUser]);

  return {
    user,
    tenantId,
    isAuthenticated,
    login,
    register,
    logout,
    refreshMe,
  };
}
