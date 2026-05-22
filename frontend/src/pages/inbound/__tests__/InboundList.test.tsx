// --- L3.9 inbound ---
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import InboundList from '../InboundList';

vi.mock('@/hooks/useInbound', () => ({
  useInboundList: () => ({
    data: [
      {
        id: 'e1',
        tenant_id: 't1',
        message_id: '<m1@ex>',
        from_address: 'jane@brokerage.example',
        from_name: 'Jane',
        to_address: 'submissions@acme.in.getonce.com',
        subject: 'AmTrust GL quote',
        received_at: '2026-05-20T13:00:00Z',
        status: 'routed',
        spam_score: 0.1,
        routing_error: null,
        attachment_count: 1,
        draft_submission_id: 's1',
        draft_supplier_id: null,
      },
    ],
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

describe('InboundList', () => {
  it('renders inbound emails returned by the hook', () => {
    render(
      <MemoryRouter>
        <InboundList />
      </MemoryRouter>,
    );
    expect(screen.getByText('AmTrust GL quote')).toBeInTheDocument();
    expect(screen.getByText('Jane')).toBeInTheDocument();
    expect(screen.getByText('Routed')).toBeInTheDocument();
  });
});

