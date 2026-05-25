/**
 * Frontend type aliases for the Once API.
 *
 * Source of truth — mirrors backend Pydantic shapes. `@/services/api`
 * re-exports the same names for backward compatibility, but new code SHOULD
 * import from this module.
 */

/* ---------------------- Core enums + auth -------------------------------- */

export type PortalPlatform =
  | "applied_epic"
  | "vertafore_ams360"
  | "vertafore_sircon"
  | "amtrust"
  | "markel"
  | "nationwide_es"
  | "cna"
  | "guidewire"
  | "hawksoft"
  | "ezlynx"
  | "nowcerts";

export type SubmissionStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "retrying"
  | "blocked"
  | "platform_unsupported";

export type ConsentScope = "read_only" | "submit_on_behalf" | "submit_and_sign";

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
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

/* ---------------------- Suppliers --------------------------------------- */

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

/* ---------------------- Portals + submissions --------------------------- */

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

/* ---------------------- Receipts + consents ----------------------------- */

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

/* ---------------------- Auth inputs + error envelopes ------------------- */

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

export type AcordFormType = "125" | "126" | "127" | "128" | "130" | "140";

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
