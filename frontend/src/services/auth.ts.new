import { api, tokenStorage } from '@/services/api';
import type {
  LoginInput,
  RegisterInput,
  TokenPair,
  UserMe,
} from '@/services/api';

const SKIP_AUTH_CONFIG = { _onceSkipAuth: true } as const;

export async function login(input: LoginInput): Promise<TokenPair> {
  const resp = await api.post<TokenPair>('/auth/login', input, SKIP_AUTH_CONFIG);
  tokenStorage.setPair(resp.data);
  return resp.data;
}

export async function register(input: RegisterInput): Promise<TokenPair> {
  const resp = await api.post<TokenPair>('/auth/register', input, SKIP_AUTH_CONFIG);
  tokenStorage.setPair(resp.data);
  return resp.data;
}

export async function refresh(): Promise<TokenPair | null> {
  const refreshToken = tokenStorage.getRefresh();
  if (!refreshToken) return null;
  try {
    const resp = await api.post<TokenPair>(
      '/auth/refresh',
      { refresh_token: refreshToken },
      SKIP_AUTH_CONFIG,
    );
    tokenStorage.setPair(resp.data);
    return resp.data;
  } catch {
    tokenStorage.clear();
    return null;
  }
}

export async function me(): Promise<UserMe> {
  const resp = await api.get<UserMe>('/auth/me');
  return resp.data;
}

export function logout(): void {
  tokenStorage.clear();
}
