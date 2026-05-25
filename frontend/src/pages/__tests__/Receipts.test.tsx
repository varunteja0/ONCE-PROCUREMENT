import { describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '@/test/utils';

vi.mock('@/hooks/useReceipts', () => ({
  useReceipts: () => ({
    data: [],
    isLoading: false,
    error: null,
  }),
}));

// ReceiptVerifierWidget pulls in WebCrypto + the verifier-keys query.
// For a minimal page test we stub it.
vi.mock('@/components/ReceiptVerifierWidget', () => ({
  default: () => null,
}));

import Receipts from '@/pages/Receipts';

describe('Receipts page (empty state)', () => {
  it('renders an EmptyState when there are no receipts', () => {
    renderWithProviders(<Receipts />);

    // Page heading is always present.
    expect(
      screen.getByRole('heading', { level: 1, name: /receipts/i }),
    ).toBeInTheDocument();

    // Both the page itself and the EmptyState component publish
    // `role="status"`. At least one status region should be present and
    // mention the empty-state copy (resilient to wording tweaks).
    const statuses = screen.getAllByRole('status');
    expect(statuses.length).toBeGreaterThan(0);
    expect(
      statuses.some((node) => /no receipts|no.*yet/i.test(node.textContent ?? '')),
    ).toBe(true);
  });
});
