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
/*  Types — mirror of backend Pydantic schemas.                              */
/*                                                                           */
/*  NOTE: these definitions should ultimately live in `src/types/api.ts`.    */
/*  They are temporarily co-located here because the file-creation tool in   */
/*  the build environment could not materialise the `src/types/` directory.  */
/*  Consumers should import from `@/services/api`; once `src/types/api.ts`   */
/*  exists, the same exports can be moved verbatim and re-exported here.     */
/* ------------------------------------------------------------------------ */

export type PortalPlatform =
  | 'applied_epic'
  | 'vertafore_ams360'
  | 'vertafore_sircon'
  | 'amtrust'
  | 'markel'
  | 'nationwide_es'
  | 'cna'
  | 'guidewire'
  | 'hawksoft'
  | 'ezlynx'
  | 'nowcerts';

export type SubmissionStatus =
  | 'queued'
  | 'running'
  | 'completed'
  | 'failed'
  | 'retrying'
  | 'blocked'
  | 'platform_unsupported';

export type ConsentScope = 'read_only' | 'submit_on_behalf' | 'submit_and_sign';

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
}

export interface UserMe {
  id: string;
  email: string;
  full_name: string | null;
  tenant_id: string;
  role: string;
}

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  plan: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SupplierAddress {
  line1?: string;
  line2?: string;
  city?: string;
  state?: string;
  postal_code?: string;
  country?: string;
  [key: string]: string | undefined;
}

export interface Supplier {
  id: string;
  tenant_id: string;
  legal_name: string;
  dba_name: string | null;
  ein: string | null;
  naics_code: string | null;
  primary_email: string | null;
  primary_phone: string | null;
  address_json: SupplierAddress | null;
  website: string | null;
  created_at: string;
  updated_at: string;
}

export interface SupplierListItem {
  id: string;
  legal_name: string;
  dba_name: string | null;
  primary_email: string | null;
  created_at: string;
}

export interface SupplierCreateInput {
  legal_name: string;
  dba_name?: string | null;
  ein?: string | null;
  naics_code?: string | null;
  primary_email?: string | null;
  primary_phone?: string | null;
  address_json?: SupplierAddress | null;
  website?: string | null;
}

export type SupplierUpdateInput = Partial<SupplierCreateInput>;

export interface Portal {
  id: string;
  platform: PortalPlatform;
  display_name: string;
  base_url: string | null;
  is_supported: boolean;
  risky: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface PortalListResponse {
  items: Portal[];
  total: number;
}

export type JsonObject = Record<string, unknown>;

export interface Submission {
  id: string;
  tenant_id: string;
  supplier_id: string;
  portal_id: string;
  status: SubmissionStatus;
  payload_json: JsonObject;
  result_json: JsonObject | null;
  attempt_count: number;
  last_error: string | null;
  claimed_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  consent_record_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface SubmissionListItem {
  id: string;
  supplier_id: string;
  portal_id: string;
  status: SubmissionStatus;
  attempt_count: number;
  last_error: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface SubmissionCreateInput {
  supplier_id: string;
  portal_id: string;
  payload: JsonObject;
  consent_record_id: string;
}

export interface Receipt {
  id: string;
  tenant_id: string;
  supplier_id: string;
  submission_id: string;
  portal_platform: string;
  submitted_at: string;
  payload_hash: string;
  tos_version_hash: string;
  consent_record_id: string;
  signing_key_id: string;
  signature_b64: string;
  public_payload_json: JsonObject;
  created_at: string;
  updated_at: string;
  verify_url: string;
}

export interface ConsentRecord {
  id: string;
  tenant_id: string;
  supplier_id: string;
  scope: ConsentScope;
  portal_ids_json: string[];
  granted_at: string;
  revoked_at: string | null;
  granted_by_user_id: string;
  signed_text: string;
  signature_b64: string;
  created_at: string;
  updated_at: string;
}

export interface LoginInput {
  email: string;
  password: string;
}

export interface RegisterInput {
  email: string;
  password: string;
  full_name: string;
  tenant_name: string;
}

export interface ApiValidationError {
  msg?: string;
  loc?: unknown[];
  type?: string;
}

export interface ApiErrorBody {
  detail?: string | ApiValidationError[];
}

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

/* Helper to issue a request that bypasses the auth header (used by login). */
export function unauthenticatedConfig(): { _onceSkipAuth: true } {
  return { _onceSkipAuth: true };
}
