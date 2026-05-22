import type * as BillingApiModule from '@/services/billingApi';
import { renderWithProviders } from '@/test/utils';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const getPricing = vi.fn();
const createCheckout = vi.fn();

vi.mock('@/services/billingApi', async () => {
  const actual = await vi.importActual<typeof BillingApiModule>(
    '@/services/billingApi',
  );
  return {
    ...actual,
    getPricing: (...a: unknown[]) => getPricing(...a),
    createCheckout: (...a: unknown[]) => createCheckout(...a),
  };
});

vi.mock('@/services/api', () => ({
  api: {},
  tokenStorage: {
    getAccess: () => 'token-123',
    getRefresh: () => null,
    setPair: vi.fn(),
    clear: vi.fn(),
  },
  extractErrorMessage: (e: unknown, fallback: string) =>
    e instanceof Error ? e.message : fallback,
}));

vi.mock('@/lib/toast', () => ({
  default: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));

import Pricing from '@/pages/Pricing';

const PRICING_DATA = {
  plan_name: 'Starter',
  plan_tagline: 'Submit once. Prove it forever.',
  prices: [
    {
      key: 'setup',
      stripe_price_id: 'price_setup',
      amount_cents: 250_000,
      currency: 'usd',
      label: 'Setup',
      description: 'One-time',
    },
    {
      key: 'monthly',
      stripe_price_id: 'price_monthly',
      amount_cents: 150_000,
      currency: 'usd',
      label: 'Monthly',
      description: 'Recurring',
    },
  ],
  features: ['Receipts'],
};

beforeEach(() => {
  getPricing.mockReset();
  createCheckout.mockReset();
});

describe('Pricing page', () => {
  it('renders pricing fetched from the API', async () => {
    getPricing.mockResolvedValueOnce(PRICING_DATA);
    renderWithProviders(<Pricing />);
    await waitFor(() =>
      expect(screen.getByText('$2,500')).toBeInTheDocument(),
    );
    expect(screen.getByText('$1,500')).toBeInTheDocument();
  });

  it('starts checkout when authed user clicks CTA', async () => {
    const origAssign = window.location.assign;
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { ...window.location, assign: vi.fn() },
    });
    getPricing.mockResolvedValueOnce(PRICING_DATA);
    createCheckout.mockResolvedValueOnce({
      checkout_url: 'https://checkout.stripe.com/c/test',
      session_id: 'cs_test_1',
    });
    renderWithProviders(<Pricing />);
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: /start checkout/i }),
      ).toBeInTheDocument(),
    );
    await userEvent.click(
      screen.getByRole('button', { name: /start checkout/i }),
    );
    await waitFor(() => expect(createCheckout).toHaveBeenCalledTimes(1));
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { ...window.location, assign: origAssign },
    });
  });

  it('shows an error banner when pricing fetch fails', async () => {
    getPricing.mockRejectedValueOnce(new Error('boom'));
    renderWithProviders(<Pricing />);
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(/boom/),
    );
  });
});
