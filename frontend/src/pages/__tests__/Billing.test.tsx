import type * as BillingApiModule from '@/services/billingApi';
import { renderWithProviders } from '@/test/utils';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const getSubscription = vi.fn();
const listInvoices = vi.fn();
const createPortal = vi.fn();
const createCheckout = vi.fn();

vi.mock('@/services/billingApi', async () => {
  const actual = await vi.importActual<typeof BillingApiModule>(
    '@/services/billingApi',
  );
  return {
    ...actual,
    getSubscription: (...a: unknown[]) => getSubscription(...a),
    listInvoices: (...a: unknown[]) => listInvoices(...a),
    createPortal: (...a: unknown[]) => createPortal(...a),
    createCheckout: (...a: unknown[]) => createCheckout(...a),
  };
});

vi.mock('@/services/api', () => ({
  api: {},
  extractErrorMessage: (e: unknown, fb: string) =>
    e instanceof Error ? e.message : fb,
}));

vi.mock('@/lib/toast', () => ({
  default: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));

import Billing from '@/pages/Billing';

beforeEach(() => {
  getSubscription.mockReset();
  listInvoices.mockReset();
  createPortal.mockReset();
  createCheckout.mockReset();
});

describe('Billing page', () => {
  it('shows subscribe CTA when no subscription exists', async () => {
    getSubscription.mockResolvedValueOnce(null);
    listInvoices.mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 25,
      offset: 0,
    });
    renderWithProviders(<Billing />);
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: /subscribe to starter/i }),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText(/no invoices yet/i)).toBeInTheDocument();
  });

  it('shows subscription details + Manage in Stripe when active', async () => {
    getSubscription.mockResolvedValueOnce({
      id: 'sub-row-1',
      tenant_id: 't-1',
      stripe_subscription_id: 'sub_test',
      status: 'active',
      current_period_start: '2026-05-01T00:00:00Z',
      current_period_end: '2026-06-01T00:00:00Z',
      cancel_at_period_end: false,
      canceled_at: null,
      plan_setup_paid: true,
      monthly_price_cents: 150_000,
      past_due_since: null,
      created_at: '2026-05-01T00:00:00Z',
      updated_at: '2026-05-01T00:00:00Z',
    });
    listInvoices.mockResolvedValueOnce({
      items: [
        {
          id: 'inv-1',
          stripe_invoice_id: 'in_1',
          status: 'paid',
          amount_due_cents: 150_000,
          amount_paid_cents: 150_000,
          currency: 'usd',
          hosted_invoice_url: 'https://stripe.test/invoice/1',
          invoice_pdf_url: null,
          due_at: null,
          paid_at: '2026-05-02T00:00:00Z',
          created_at: '2026-05-02T00:00:00Z',
        },
      ],
      total: 1,
      limit: 25,
      offset: 0,
    });
    renderWithProviders(<Billing />);
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: /manage in stripe/i }),
      ).toBeInTheDocument(),
    );
    expect(screen.getAllByText(/active/i).length).toBeGreaterThan(0);
    expect(screen.getByRole('link', { name: /view/i })).toHaveAttribute(
      'href',
      'https://stripe.test/invoice/1',
    );
  });

  it('opens Stripe portal when Manage in Stripe is clicked', async () => {
    getSubscription.mockResolvedValueOnce({
      id: 'sub-row-1',
      tenant_id: 't-1',
      stripe_subscription_id: 'sub_test',
      status: 'active',
      current_period_start: null,
      current_period_end: null,
      cancel_at_period_end: false,
      canceled_at: null,
      plan_setup_paid: true,
      monthly_price_cents: 150_000,
      past_due_since: null,
      created_at: '2026-05-01T00:00:00Z',
      updated_at: '2026-05-01T00:00:00Z',
    });
    listInvoices.mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 25,
      offset: 0,
    });
    createPortal.mockResolvedValueOnce({
      portal_url: 'https://billing.stripe.com/p/test',
    });
    const assign = vi.fn();
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { ...window.location, assign },
    });
    renderWithProviders(<Billing />);
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: /manage in stripe/i }),
      ).toBeInTheDocument(),
    );
    await userEvent.click(
      screen.getByRole('button', { name: /manage in stripe/i }),
    );
    await waitFor(() => expect(createPortal).toHaveBeenCalledTimes(1));
  });
});
