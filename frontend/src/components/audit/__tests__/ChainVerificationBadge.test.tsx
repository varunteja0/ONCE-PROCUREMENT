// --- L3.10 audit ---
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

const useChainVerification = vi.fn();
vi.mock('@/hooks/useAudit', () => ({
  useChainVerification: (...args: unknown[]) => useChainVerification(...args),
}));

import { ChainVerificationBadge } from '@/components/audit/ChainVerificationBadge';

describe('ChainVerificationBadge', () => {
  it('renders a verified badge when chain is valid', () => {
    useChainVerification.mockReturnValue({
      data: { valid: true, rows_checked: 42, breaks: [] },
      isLoading: false,
      isError: false,
    });
    render(<ChainVerificationBadge />);
    const badge = screen.getByTestId('chain-verification-badge');
    expect(badge.dataset.tone).toBe('ok');
    expect(badge).toHaveTextContent(/chain verified · 42/i);
  });

  it('renders a tampered badge when the chain has breaks', () => {
    useChainVerification.mockReturnValue({
      data: { valid: false, rows_checked: 5, breaks: [{ position: 3 }, { position: 4 }] },
      isLoading: false,
      isError: false,
    });
    render(<ChainVerificationBadge />);
    const badge = screen.getByTestId('chain-verification-badge');
    expect(badge.dataset.tone).toBe('bad');
    expect(badge).toHaveTextContent(/chain tampered · 2 breaks/i);
  });

  it('renders a pending badge while loading', () => {
    useChainVerification.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });
    render(<ChainVerificationBadge />);
    const badge = screen.getByTestId('chain-verification-badge');
    expect(badge.dataset.tone).toBe('pending');
    expect(badge).toHaveTextContent(/verifying/i);
  });
});
