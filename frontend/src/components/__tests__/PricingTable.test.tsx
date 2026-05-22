import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import PricingTableComponent from '@/components/PricingTable';
import type { PricingTable as PricingTableData } from '@/services/billingApi';

const data: PricingTableData = {
  plan_name: 'Starter',
  plan_tagline: 'Submit once. Prove it forever.',
  prices: [
    {
      key: 'setup',
      stripe_price_id: 'price_setup',
      amount_cents: 250_000,
      currency: 'usd',
      label: 'Setup',
      description: 'One-time onboarding',
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
  features: ['Unlimited submissions', 'Audit-grade receipts'],
};

describe('PricingTable', () => {
  it('renders plan name, both prices, and features', () => {
    render(
      <PricingTableComponent data={data} ctaLabel="Start checkout" onCtaClick={() => {}} />,
    );
    expect(screen.getByRole('heading', { name: /starter/i })).toBeInTheDocument();
    expect(screen.getByText('$2,500')).toBeInTheDocument();
    expect(screen.getByText('$1,500')).toBeInTheDocument();
    expect(screen.getByText(/unlimited submissions/i)).toBeInTheDocument();
    expect(screen.getByText(/audit-grade receipts/i)).toBeInTheDocument();
  });

  it('fires onCtaClick when CTA pressed', async () => {
    const onClick = vi.fn();
    render(
      <PricingTableComponent data={data} ctaLabel="Start checkout" onCtaClick={onClick} />,
    );
    await userEvent.click(screen.getByRole('button', { name: /start checkout/i }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('disables CTA when ctaLoading=true and shows loading label', () => {
    render(
      <PricingTableComponent
        data={data}
        ctaLabel="Start checkout"
        onCtaClick={() => {}}
        ctaLoading
      />,
    );
    const btn = screen.getByRole('button');
    expect(btn).toBeDisabled();
    expect(btn).toHaveTextContent(/loading/i);
  });
});
