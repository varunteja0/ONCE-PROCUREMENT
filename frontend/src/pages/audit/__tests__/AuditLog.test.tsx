// --- L3.10 audit ---
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

const useAuditList = vi.fn();
const useChainVerification = vi.fn();

vi.mock('@/hooks/useAudit', () => ({
  useAuditList: (...args: unknown[]) => useAuditList(...args),
  useChainVerification: (...args: unknown[]) => useChainVerification(...args),
}));

import AuditLog from '@/pages/audit/AuditLog';

function renderPage(): void {
  render(
    <MemoryRouter>
      <AuditLog />
    </MemoryRouter>,
  );
}

describe('AuditLog page', () => {
  it('renders heading, badge, filters and timeline rows', () => {
    useChainVerification.mockReturnValue({
      data: { valid: true, rows_checked: 3, breaks: [] },
      isLoading: false,
      isError: false,
    });
    useAuditList.mockReturnValue({
      data: {
        total: 1,
        items: [
          {
            id: 'r1',
            tenant_id: 't1',
            chain_position: 1,
            prev_hash: '0'.repeat(64),
            this_hash: 'a'.repeat(64),
            occurred_at: '2026-05-21T12:00:00Z',
            actor_type: 'user',
            actor_email: 'alice@example.com',
            actor_id: 'u1',
            action_verb: 'created',
            resource_type: 'supplier',
            resource_id: 's1',
            request_id: null,
            ip_address: null,
            user_agent: null,
            before_redacted: null,
            after_redacted: null,
            metadata: null,
          },
        ],
      },
      isLoading: false,
      isError: false,
    });

    renderPage();
    expect(screen.getByRole('heading', { name: /audit log/i })).toBeInTheDocument();
    expect(screen.getByTestId('chain-verification-badge')).toBeInTheDocument();
    expect(screen.getByTestId('filter-actor')).toBeInTheDocument();
    expect(screen.getByTestId('filter-resource')).toBeInTheDocument();
    expect(screen.getByText('alice@example.com')).toBeInTheDocument();
    expect(screen.getByText(/showing 1 of 1 events/i)).toBeInTheDocument();
  });

  it('passes selected filters through to useAuditList', async () => {
    useChainVerification.mockReturnValue({
      data: { valid: true, rows_checked: 0, breaks: [] },
      isLoading: false,
      isError: false,
    });
    useAuditList.mockReturnValue({
      data: { total: 0, items: [] },
      isLoading: false,
      isError: false,
    });

    renderPage();
    const user = userEvent.setup();
    await user.selectOptions(screen.getByTestId('filter-actor'), 'system');
    await user.type(screen.getByTestId('filter-resource'), 'supplier');

    // The hook is called on every render; the last call carries the latest filters.
    const lastCall = useAuditList.mock.calls.at(-1)?.[0];
    expect(lastCall).toMatchObject({
      limit: 100,
      actor_type: 'system',
      resource_type: 'supplier',
    });
  });
});
