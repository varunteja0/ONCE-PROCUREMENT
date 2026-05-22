// Cockpit API client — separate axios instance so the operator surface
// never accidentally shares interceptors / refresh state with the tenant
// surface in src/services/api.ts.
//
// Token storage uses dedicated keys (`once.cockpit.access` / refresh) so
// signing into the cockpit cannot poison a tenant-user session, and vice
// versa.
import axios, { AxiosHeaders } from 'axios';
import type {
  AxiosError,
  AxiosInstance,
  InternalAxiosRequestConfig,
} from 'axios';

declare module 'axios' {
  /* eslint-disable @typescript-eslint/naming-convention */
  export interface AxiosRequestConfig {
    _cockpitSkipAuth?: boolean;
    _cockpitRetried?: boolean;
  }
  export interface InternalAxiosRequestConfig {
    _cockpitSkipAuth?: boolean;
    _cockpitRetried?: boolean;
  }
  /* eslint-enable @typescript-eslint/naming-convention */
}

/* ----------------------------------------------------------------------- */
/*  Types — mirror of backend Pydantic schemas (cockpit surface).          */
/* ----------------------------------------------------------------------- */

export type OperatorRole = 'founder' | 'engineering' | 'support';
export type OperatorStatus = 'active' | 'suspended';

export interface OperatorTokenPair {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  expires_in: number;
}

export interface OperatorMe {
  id: string;
  email: string;
  role: OperatorRole;
  status: OperatorStatus;
  mfa_required: boolean;
  last_login_at: string | null;
  created_at: string;
  accessible_tenant_ids: string[];
  all_tenants: boolean;
}

export interface OperatorLoginInput {
  email: string;
  password: string;
  totp_code?: string;
}

export interface CockpitTenantSummary {
  id: string;
  name: string;
  slug: string;
  plan: string;
  is_active: boolean;
  created_at: string;
  supplier_count: number;
  submission_count: number;
  last_activity_at: string | null;
}

export interface CockpitTenantListResponse {
  items: CockpitTenantSummary[];
  total: number;
}

export interface CockpitAuditEntry {
  id: string;
  operator_id: string | null;
  tenant_id_acted_as: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  request_id: string | null;
  method: string | null;
  path: string | null;
  status_code: number | null;
  ip: string | null;
  user_agent: string | null;
  payload_redacted: Record<string, unknown> | null;
  occurred_at: string;
}

export interface CockpitAuditListResponse {
  items: CockpitAuditEntry[];
  total: number;
}

export interface CockpitActAsResponse {
  tenant_id: string;
  tenant_name: string;
  permission: string;
  expires_in: number;
}

/* ----------------------------------------------------------------------- */
/*  Token storage                                                          */
/* ----------------------------------------------------------------------- */

export const COCKPIT_ACCESS_KEY = 'once.cockpit.access';
export const COCKPIT_REFRESH_KEY = 'once.cockpit.refresh';
export const COCKPIT_OPERATOR_KEY = 'once.cockpit.operator';
export const COCKPIT_ACTING_AS_KEY = 'once.cockpit.actingAs';

export const cockpitTokenStorage = {
  getAccess(): string | null {
    try {
      return localStorage.getItem(COCKPIT_ACCESS_KEY);
    } catch {
      return null;
    }
  },
  getRefresh(): string | null {
    try {
      return localStorage.getItem(COCKPIT_REFRESH_KEY);
    } catch {
      return null;
    }
  },
  setPair(pair: OperatorTokenPair): void {
    try {
      localStorage.setItem(COCKPIT_ACCESS_KEY, pair.access_token);
      localStorage.setItem(COCKPIT_REFRESH_KEY, pair.refresh_token);
    } catch {
      /* ignore */
    }
  },
  clear(): void {
    try {
      localStorage.removeItem(COCKPIT_ACCESS_KEY);
      localStorage.removeItem(COCKPIT_REFRESH_KEY);
    } catch {
      /* ignore */
    }
  },
};

/* ----------------------------------------------------------------------- */
/*  Axios instance                                                         */
/* ----------------------------------------------------------------------- */

function resolveBaseUrl(): string {
  const raw: unknown = import.meta.env.VITE_COCKPIT_API_BASE;
  return typeof raw === 'string' && raw.length > 0 ? raw : '/cockpit';
}

const baseURL: string = resolveBaseUrl();

export const cockpitApi: AxiosInstance = axios.create({
  baseURL,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

type RetriableConfig = InternalAxiosRequestConfig;

cockpitApi.interceptors.request.use((config) => {
  const cfg = config as RetriableConfig;
  if (cfg._cockpitSkipAuth) return cfg;
  const token = cockpitTokenStorage.getAccess();
  if (token) {
    const headers =
      cfg.headers instanceof AxiosHeaders
        ? cfg.headers
        : new AxiosHeaders(cfg.headers);
    headers.set('Authorization', `Bearer ${token}`);
    cfg.headers = headers;
  }
  // Stamp X-Operator-Acting-Tenant from session storage if the SPA has set it.
  try {
    const actingAs = localStorage.getItem(COCKPIT_ACTING_AS_KEY);
    if (actingAs) {
      const headers =
        cfg.headers instanceof AxiosHeaders
          ? cfg.headers
          : new AxiosHeaders(cfg.headers);
      headers.set('X-Operator-Acting-Tenant', actingAs);
      cfg.headers = headers;
    }
  } catch {
    /* ignore */
  }
  return cfg;
});

let refreshInFlight: Promise<OperatorTokenPair | null> | null = null;

async function performRefresh(): Promise<OperatorTokenPair | null> {
  const refreshToken = cockpitTokenStorage.getRefresh();
  if (!refreshToken) return null;
  try {
    const resp = await axios.post<OperatorTokenPair>(
      `${baseURL.replace(/\/$/, '')}/auth/refresh`,
      { refresh_token: refreshToken },
      { headers: { 'Content-Type': 'application/json' } },
    );
    cockpitTokenStorage.setPair(resp.data);
    return resp.data;
  } catch {
    return null;
  }
}

function redirectToCockpitLogin(): void {
  if (typeof window === 'undefined') return;
  if (window.location.pathname.startsWith('/cockpit/login')) return;
  window.location.assign('/cockpit/login');
}

cockpitApi.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetriableConfig | undefined;
    const status = error.response?.status;
    if (
      status !== 401 ||
      !original ||
      original._cockpitRetried ||
      original._cockpitSkipAuth ||
      original.url?.includes('/auth/refresh') ||
      original.url?.includes('/auth/login')
    ) {
      return Promise.reject(error);
    }
    original._cockpitRetried = true;
    if (!refreshInFlight) {
      refreshInFlight = performRefresh().finally(() => {
        refreshInFlight = null;
      });
    }
    const pair = await refreshInFlight;
    if (!pair) {
      cockpitTokenStorage.clear();
      redirectToCockpitLogin();
      return Promise.reject(error);
    }
    const headers =
      original.headers instanceof AxiosHeaders
        ? original.headers
        : new AxiosHeaders(original.headers);
    headers.set('Authorization', `Bearer ${pair.access_token}`);
    original.headers = headers;
    return cockpitApi.request(original);
  },
);

/* ----------------------------------------------------------------------- */
/*  API surface                                                            */
/* ----------------------------------------------------------------------- */

export async function cockpitLogin(
  input: OperatorLoginInput,
): Promise<OperatorTokenPair> {
  const resp = await cockpitApi.post<OperatorTokenPair>('/auth/login', input, {
    _cockpitSkipAuth: true,
  } as unknown as Record<string, unknown>);
  cockpitTokenStorage.setPair(resp.data);
  return resp.data;
}

export async function cockpitMe(): Promise<OperatorMe> {
  const resp = await cockpitApi.get<OperatorMe>('/auth/me');
  return resp.data;
}

export async function cockpitLogout(): Promise<void> {
  const refresh = cockpitTokenStorage.getRefresh();
  if (refresh) {
    try {
      await cockpitApi.post('/auth/logout', { refresh_token: refresh });
    } catch {
      /* ignore */
    }
  }
  cockpitTokenStorage.clear();
}

export async function cockpitListTenants(): Promise<CockpitTenantListResponse> {
  const resp = await cockpitApi.get<CockpitTenantListResponse>('/tenants');
  return resp.data;
}

export async function cockpitGetTenant(
  tenantId: string,
): Promise<CockpitTenantSummary> {
  const resp = await cockpitApi.get<CockpitTenantSummary>(
    `/tenants/${encodeURIComponent(tenantId)}`,
  );
  return resp.data;
}

export async function cockpitActAs(
  tenantId: string,
): Promise<CockpitActAsResponse> {
  const resp = await cockpitApi.post<CockpitActAsResponse>('/tenants/act-as', {
    tenant_id: tenantId,
  });
  return resp.data;
}

export async function cockpitListAudit(params: {
  limit?: number;
  offset?: number;
  operator_id?: string;
  tenant_id?: string;
} = {}): Promise<CockpitAuditListResponse> {
  const resp = await cockpitApi.get<CockpitAuditListResponse>('/audit', {
    params,
  });
  return resp.data;
}
