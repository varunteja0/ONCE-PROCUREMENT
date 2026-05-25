/**
 * Auth API surface — thin wrappers around `@/services/auth` that callers
 * (TanStack Query hooks, route guards) should import from instead of
 * reaching into the service module directly. Keeping the layer separate
 * makes it easier to swap the transport (e.g. fetch → axios → tRPC) without
 * touching call sites.
 */
import {
  login as loginService,
  logout as logoutService,
  me as meService,
  refresh as refreshService,
} from '@/services/auth';
import type {
  LoginInput,
  TokenPair,
  UserMe,
} from '@/types/api';

export const apiAuth = {
  me(): Promise<UserMe> {
    return meService();
  },
  login(input: LoginInput): Promise<TokenPair> {
    return loginService(input);
  },
  logout(): void {
    logoutService();
  },
  refresh(): Promise<TokenPair | null> {
    return refreshService();
  },
};

export type ApiAuth = typeof apiAuth;
