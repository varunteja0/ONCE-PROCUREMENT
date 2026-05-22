// --- L3.6 onboarding ---
import axios, { AxiosHeaders, type AxiosInstance } from 'axios';
import type { TokenPair } from '@/services/api';

export const ONBOARDING_TOKEN_KEY = 'once.onboarding_token';

export interface OnboardingStartInput {
  email: string;
  password: string;
  company_name: string;
  website_url?: string;
}

export interface OnboardingStartResponse {
  onboarding_session_token: string;
  tenant_id: string;
  expires_in_seconds: number;
  dev_verification_code?: string | null;
}

export interface VerifyEmailResponse extends TokenPair {
  tenant_id: string;
  current_step: OnboardingStep;
}

export type OnboardingStep =
  | 'start'
  | 'email_verify'
  | 'profile'
  | 'plan'
  | 'portal'
  | 'supplier'
  | 'submission'
  | 'done';

export type SkippableStep = 'plan' | 'portal' | 'supplier' | 'submission';

export interface OnboardingStateRead {
  tenant_id: string;
  current_step: OnboardingStep;
  completed_steps: Record<string, unknown>;
  skipped_steps: Record<string, unknown>;
  company_profile_json: Record<string, unknown> | null;
  started_at: string;
  last_activity_at: string;
  completed_at: string | null;
}

export interface CompanyProfileInput {
  legal_name: string;
  fein: string;
  naic_code?: string;
  primary_state: string;
  employees?: number;
  gwp_band?: string;
  role_in_mga?: string;
}

export interface ConnectPortalInput {
  portal_id: string;
  username: string;
  password: string;
}

export interface AddSupplierInput {
  legal_name: string;
  fein?: string;
  state: string;
  primary_email?: string;
}

export interface RunFirstSubmissionInput {
  supplier_id: string;
  portal_id: string;
}

export interface SubmissionPollRead {
  submission_id: string;
  status: string;
}

export interface OnboardingCompleteResponse {
  tenant_id: string;
  dashboard_url: string;
  current_step: OnboardingStep;
}

export const onboardingTokenStorage = {
  get(): string | null {
    try {
      return localStorage.getItem(ONBOARDING_TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(token: string): void {
    try {
      localStorage.setItem(ONBOARDING_TOKEN_KEY, token);
    } catch {
      /* ignore */
    }
  },
  clear(): void {
    try {
      localStorage.removeItem(ONBOARDING_TOKEN_KEY);
    } catch {
      /* ignore */
    }
  },
};

function resolveBaseUrl(): string {
  const raw: unknown = import.meta.env.VITE_API_BASE;
  return typeof raw === 'string' && raw.length > 0 ? raw : '/v1';
}

const onboardingApi: AxiosInstance = axios.create({
  baseURL: resolveBaseUrl(),
  headers: { 'Content-Type': 'application/json' },
});

onboardingApi.interceptors.request.use((config) => {
  const token = onboardingTokenStorage.get();
  if (token) {
    const headers =
      config.headers instanceof AxiosHeaders
        ? config.headers
        : new AxiosHeaders(config.headers);
    headers.set('Authorization', `Bearer ${token}`);
    config.headers = headers;
  }
  return config;
});

export const onboarding = {
  async start(input: OnboardingStartInput): Promise<OnboardingStartResponse> {
    const r = await onboardingApi.post<OnboardingStartResponse>(
      '/onboarding/start',
      input,
    );
    if (r.data.onboarding_session_token) {
      onboardingTokenStorage.set(r.data.onboarding_session_token);
    }
    return r.data;
  },
  async verifyEmail(code: string): Promise<VerifyEmailResponse> {
    const r = await onboardingApi.post<VerifyEmailResponse>(
      '/onboarding/verify-email',
      { code },
    );
    return r.data;
  },
  async state(): Promise<OnboardingStateRead> {
    const r = await onboardingApi.get<OnboardingStateRead>('/onboarding/state');
    return r.data;
  },
  async companyProfile(input: CompanyProfileInput): Promise<OnboardingStateRead> {
    const r = await onboardingApi.post<OnboardingStateRead>(
      '/onboarding/company-profile',
      input,
    );
    return r.data;
  },
  async connectPortal(input: ConnectPortalInput): Promise<OnboardingStateRead> {
    const r = await onboardingApi.post<OnboardingStateRead>(
      '/onboarding/connect-portal',
      input,
    );
    return r.data;
  },
  async addSupplier(input: AddSupplierInput): Promise<OnboardingStateRead> {
    const r = await onboardingApi.post<OnboardingStateRead>(
      '/onboarding/add-supplier',
      input,
    );
    return r.data;
  },
  async runFirstSubmission(input: RunFirstSubmissionInput): Promise<SubmissionPollRead> {
    const r = await onboardingApi.post<SubmissionPollRead>(
      '/onboarding/run-first-submission',
      input,
    );
    return r.data;
  },
  async skipStep(step: SkippableStep): Promise<OnboardingStateRead> {
    const r = await onboardingApi.post<OnboardingStateRead>(
      '/onboarding/skip-step',
      { step },
    );
    return r.data;
  },
  async complete(): Promise<OnboardingCompleteResponse> {
    const r = await onboardingApi.post<OnboardingCompleteResponse>(
      '/onboarding/complete',
    );
    return r.data;
  },
};

export default onboarding;
// --- /L3.6 onboarding ---
