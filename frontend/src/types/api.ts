/**
 * Frontend type aliases for the Once API.
 *
 * Mirrors backend Pydantic shapes. The legacy `@/services/api` module also
 * re-exports many of these for backward compatibility; new code SHOULD
 * import from this module.
 */

export type {
  PortalPlatform,
  SubmissionStatus,
  ConsentScope,
  TokenPair,
  UserMe,
  Tenant,
  Supplier,
  SupplierAddress,
  SupplierListItem,
  SupplierCreateInput,
  SupplierUpdateInput,
  Portal,
  PortalListResponse,
  Submission,
  SubmissionListItem,
  SubmissionCreateInput,
  Receipt,
  ConsentRecord,
  LoginInput,
  RegisterInput,
  JsonObject,
} from '@/services/api';

/* ---------------------- L2.6 — new first-class entities ------------------ */

export interface PagedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Coi {
  id: string;
  tenant_id: string;
  supplier_id: string;
  carrier: string;
  policy_number: string | null;
  effective_date: string | null;
  expires_at: string;
  coverage_type: string | null;
  limit_amount: string | null;
  file_url: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface CoiCreateInput {
  supplier_id: string;
  carrier: string;
  policy_number?: string | null;
  effective_date?: string | null;
  expires_at: string;
  coverage_type?: string | null;
  limit_amount?: string | null;
  file_url?: string | null;
  notes?: string | null;
}

export interface LossRun {
  id: string;
  tenant_id: string;
  supplier_id: string;
  period_start: string;
  period_end: string;
  carrier: string | null;
  total_claims: number | null;
  total_incurred: string | null;
  file_url: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface LossRunCreateInput {
  supplier_id: string;
  period_start: string;
  period_end: string;
  carrier?: string | null;
  total_claims?: number | null;
  total_incurred?: string | null;
  file_url?: string | null;
  notes?: string | null;
}

export interface ProducerLicense {
  id: string;
  tenant_id: string;
  supplier_id: string;
  state: string;
  license_number: string;
  license_type: string | null;
  expires_at: string;
  file_url: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProducerLicenseCreateInput {
  supplier_id: string;
  state: string;
  license_number: string;
  license_type?: string | null;
  expires_at: string;
  file_url?: string | null;
  notes?: string | null;
}

export interface EoCertificate {
  id: string;
  tenant_id: string;
  supplier_id: string;
  carrier: string;
  policy_number: string | null;
  limit_amount: string;
  retroactive_date: string | null;
  expires_at: string;
  file_url: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface EoCertificateCreateInput {
  supplier_id: string;
  carrier: string;
  policy_number?: string | null;
  limit_amount: string;
  retroactive_date?: string | null;
  expires_at: string;
  file_url?: string | null;
  notes?: string | null;
}

export type AcordFormType = '125' | '126' | '127' | '128' | '130' | '140';

export interface AcordForm {
  id: string;
  tenant_id: string;
  supplier_id: string;
  form_type: AcordFormType;
  payload: Record<string, unknown>;
  pdf_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface AcordFormCreateInput {
  supplier_id: string;
  form_type: AcordFormType;
  payload: Record<string, unknown>;
  pdf_url?: string | null;
}

export interface RiskSchedule {
  id: string;
  tenant_id: string;
  supplier_id: string;
  line_of_business: string;
  payload: Record<string, unknown>;
  effective_date: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface RiskScheduleCreateInput {
  supplier_id: string;
  line_of_business: string;
  payload: Record<string, unknown>;
  effective_date?: string | null;
  notes?: string | null;
}
