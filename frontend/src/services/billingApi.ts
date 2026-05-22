// Billing API client — wraps tenant-scoped Stripe billing endpoints.
//
// All requests go through the shared `api` axios instance (Bearer auth +
// refresh interceptor). The backend exposes:
//   GET  /v1/billing/pricing           (public)
//   POST /v1/billing/checkout          (auth)
//   POST /v1/billing/portal            (auth, 409 when no customer)
//   GET  /v1/billing/subscription      (auth, 404 when none)
//   GET  /v1/billing/invoices          (auth, paginated, tenant-scoped)
import { api } from '@/services/api';

export type SubscriptionStatusValue =
  | 'incomplete'
  | 'incomplete_expired'
  | 'trialing'
  | 'active'
  | 'past_due'
  | 'canceled'
  | 'unpaid'
  | 'paused';

export interface BillingPrice {
  key: string;
  stripe_price_id: string | null;
  amount_cents: number;
  currency: string;
  label: string;
  description: string;
}

export interface PricingTable {
  plan_name: string;
  plan_tagline: string;
  prices: BillingPrice[];
  features: string[];
}

export interface CheckoutResponse {
  checkout_url: string;
  session_id: string;
}

export interface PortalResponse {
  portal_url: string;
}

export interface SubscriptionRead {
  id: string;
  tenant_id: string;
  stripe_subscription_id: string;
  status: SubscriptionStatusValue;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  canceled_at: string | null;
  plan_setup_paid: boolean;
  monthly_price_cents: number;
  past_due_since: string | null;
  created_at: string;
  updated_at: string;
}

export interface InvoiceRead {
  id: string;
  stripe_invoice_id: string;
  status: string;
  amount_due_cents: number;
  amount_paid_cents: number;
  currency: string;
  hosted_invoice_url: string | null;
  invoice_pdf_url: string | null;
  due_at: string | null;
  paid_at: string | null;
  created_at: string;
}

export interface InvoiceListResponse {
  items: InvoiceRead[];
  total: number;
  limit: number;
  offset: number;
}

export async function getPricing(): Promise<PricingTable> {
  const resp = await api.get<PricingTable>('/billing/pricing');
  return resp.data;
}

export async function createCheckout(
  plan: 'starter' = 'starter',
): Promise<CheckoutResponse> {
  const resp = await api.post<CheckoutResponse>('/billing/checkout', { plan });
  return resp.data;
}

export async function createPortal(): Promise<PortalResponse> {
  const resp = await api.post<PortalResponse>('/billing/portal');
  return resp.data;
}

export async function getSubscription(): Promise<SubscriptionRead | null> {
  try {
    const resp = await api.get<SubscriptionRead>('/billing/subscription');
    return resp.data;
  } catch (err: unknown) {
    // Tolerate 404 from the backend (no subscription yet) so callers don't
    // need to special-case axios errors in every screen.
    const e = err as { response?: { status?: number } };
    if (e?.response?.status === 404) return null;
    throw err;
  }
}

export async function listInvoices(
  params: { limit?: number; offset?: number } = {},
): Promise<InvoiceListResponse> {
  const resp = await api.get<InvoiceListResponse>('/billing/invoices', {
    params: { limit: params.limit ?? 25, offset: params.offset ?? 0 },
  });
  return resp.data;
}

export function formatMoneyCents(cents: number, currency = 'usd'): string {
  const dollars = cents / 100;
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency.toUpperCase(),
    minimumFractionDigits: dollars % 1 === 0 ? 0 : 2,
  }).format(dollars);
}
