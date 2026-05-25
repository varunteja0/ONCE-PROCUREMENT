import axios, { AxiosHeaders } from 'axios';
import type {
  AxiosError,
  AxiosInstance,
  InternalAxiosRequestConfig,
} from 'axios';

declare module 'axios' {
  // Augment the request config so callers can opt out of the auth interceptor
  // (login / register / refresh) and so the response interceptor can mark a
  // request as already-retried.
  /* eslint-disable @typescript-eslint/naming-convention */
  export interface AxiosRequestConfig {
    _onceSkipAuth?: boolean;
    _onceRetried?: boolean;
  }
  export interface InternalAxiosRequestConfig {
    _onceSkipAuth?: boolean;
    _onceRetried?: boolean;
  }
  /* eslint-enable @typescript-eslint/naming-convention */
}


/* ------------------------------------------------------------------------ */
/*  Types — re-exported from @/types/api for back-compat.                    */
/*  New code SHOULD import directly from `@/types/api`.                      */
/* ------------------------------------------------------------------------ */

export type * from '@/types/api';

// Local-only type aliases needed inside this module for the interceptor
// and refresh logic below. Kept here (not re-exported from types) to avoid
// type-only consumers having to import them.
import type {
  ApiErrorBody,
  TokenPair,
} from '@/types/api';

/* ------------------------------------------------------------------------ */
/*  Token storage                                                            */
/* ------------------------------------------------------------------------ */

export const ACCESS_TOKEN_KEY = 'once.access';
export const REFRESH_TOKEN_KEY = 'once.refresh';

export const tokenStorage = {
  getAccess(): string | null {
    try {
      return localStorage.getItem(ACCESS_TOKEN_KEY);
    } catch {
      return null;
    }
  },
  getRefresh(): string | null {
    try {
      return localStorage.getItem(REFRESH_TOKEN_KEY);
    } catch {
      return null;
    }
  },
  setPair(pair: TokenPair): void {
    try {
      localStorage.setItem(ACCESS_TOKEN_KEY, pair.access_token);
      localStorage.setItem(REFRESH_TOKEN_KEY, pair.refresh_token);
    } catch {
      /* storage disabled — ignore */
    }
  },
  clear(): void {
    try {
      localStorage.removeItem(ACCESS_TOKEN_KEY);
      localStorage.removeItem(REFRESH_TOKEN_KEY);
    } catch {
      /* ignore */
    }
  },
};

/* ------------------------------------------------------------------------ */
/*  Axios instance                                                           */
/* ------------------------------------------------------------------------ */

function resolveBaseUrl(): string {
  const raw: unknown = import.meta.env.VITE_API_BASE;
  return typeof raw === 'string' && raw.length > 0 ? raw : '/v1';
}

const baseURL: string = resolveBaseUrl();

export const api: AxiosInstance = axios.create({
  baseURL,
  // Enabled so the backend can roll cookie-based auth in front of the
  // existing Authorization-header flow without a coordinated frontend
  // release. Backend remains the source of truth for which auth path is
  // active; sending cookies costs nothing when the server doesn't set any.
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

/* Custom flag on the request config to mark a request as already-retried. */
type RetriableRequestConfig = InternalAxiosRequestConfig;


api.interceptors.request.use((config) => {
  const cfg = config as RetriableRequestConfig;
  if (cfg._onceSkipAuth) {
    return cfg;
  }
  const token = tokenStorage.getAccess();
  if (token) {
    const headers =
      cfg.headers instanceof AxiosHeaders
        ? cfg.headers
        : new AxiosHeaders(cfg.headers);
    headers.set('Authorization', `Bearer ${token}`);
    cfg.headers = headers;
  }
  return cfg;
});

/* ------------------------------------------------------------------------ */
/*  Refresh handling                                                         */
/* ------------------------------------------------------------------------ */

let refreshInFlight: Promise<TokenPair | null> | null = null;

function redirectToLogin(): void {
  if (typeof window === 'undefined') return;
  if (window.location.pathname === '/login') return;
  window.location.assign('/login');
}

async function performRefresh(): Promise<TokenPair | null> {
  const refreshToken = tokenStorage.getRefresh();
  if (!refreshToken) return null;
  try {
    const resp = await axios.post<TokenPair>(
      `${baseURL.replace(/\/$/, '')}/auth/refresh`,
      { refresh_token: refreshToken },
      { headers: { 'Content-Type': 'application/json' } },
    );
    tokenStorage.setPair(resp.data);
    return resp.data;
  } catch {
    return null;
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetriableRequestConfig | undefined;
    const status = error.response?.status;

    if (
      status !== 401 ||
      !original ||
      original._onceRetried ||
      original._onceSkipAuth ||
      original.url?.includes('/auth/refresh') ||
      original.url?.includes('/auth/login') ||
      original.url?.includes('/auth/register')
    ) {
      return Promise.reject(error);
    }

    original._onceRetried = true;

    if (!refreshInFlight) {
      refreshInFlight = performRefresh().finally(() => {
        refreshInFlight = null;
      });
    }
    const newPair = await refreshInFlight;

    if (!newPair) {
      tokenStorage.clear();
      redirectToLogin();
      return Promise.reject(error);
    }

    const headers =
      original.headers instanceof AxiosHeaders
        ? original.headers
        : new AxiosHeaders(original.headers);
    headers.set('Authorization', `Bearer ${newPair.access_token}`);
    original.headers = headers;

    return api.request(original);
  },
);

/* ------------------------------------------------------------------------ */
/*  Error helpers                                                            */
/* ------------------------------------------------------------------------ */

export function extractErrorMessage(err: unknown, fallback = 'Request failed'): string {
  if (axios.isAxiosError(err)) {
    const body = err.response?.data as ApiErrorBody | undefined;
    if (body?.detail) {
      if (typeof body.detail === 'string') return body.detail;
      if (Array.isArray(body.detail) && body.detail.length > 0) {
        const first = body.detail[0];
        if (first?.msg) return first.msg;
      }
    }
    return err.message || fallback;
  }
  if (err instanceof Error) return err.message;
  return fallback;
}

export function isApiError(err: unknown): err is AxiosError {
  return axios.isAxiosError(err);
}

export function isApiCancel(err: unknown): boolean {
  return axios.isCancel(err);
}

/* Helper to issue a request that bypasses the auth header (used by login). */
export function unauthenticatedConfig(): { _onceSkipAuth: true } {
  return { _onceSkipAuth: true };
}
