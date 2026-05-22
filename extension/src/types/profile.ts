/**
 * Supplier profile types — local-vault representation that mirrors the
 * backend `SupplierRead` schema (`backend/app/schemas/supplier.py`) with
 * additional insurance-specific fields kept entirely client-side until
 * a submission is dispatched.
 *
 * The extension stores these objects inside the encrypted IndexedDB vault
 * (`lib/vault.ts`) so that PII (EIN, NPN, COI numbers) never lives in
 * plaintext on disk.
 */

export interface SupplierAddress {
  line1: string;
  line2?: string;
  city: string;
  region: string;
  postal_code: string;
  country: string;
}

export interface SupplierCOI {
  carrier: string;
  policy_number: string;
  /** ISO-8601 date string (`YYYY-MM-DD`). */
  expiry: string;
  limit_each_occurrence: number;
  limit_aggregate: number;
}

export interface SupplierProfile {
  legal_name: string;
  dba_name?: string;
  ein?: string;
  naics_code?: string;
  primary_email: string;
  primary_phone?: string;
  address?: SupplierAddress;
  website?: string;
  coi?: SupplierCOI;
  lines_of_business?: string[];
  license_states?: string[];
  npn?: string;
}

export function isSupplierProfile(value: unknown): value is SupplierProfile {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.legal_name === "string" &&
    v.legal_name.length > 0 &&
    typeof v.primary_email === "string" &&
    v.primary_email.length > 0
  );
}
