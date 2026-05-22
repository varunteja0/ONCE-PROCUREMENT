// --- L3.10 audit ---
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { AuditTimeline } from '@/components/audit/AuditTimeline';
import type { AuditLogRead } from '@/services/auditApi';

function row(overrides: Partial<AuditLogRead> = {}): AuditLogRead {
  return {
    id: '01HXAUDIT1',
    tenant_id: 't1',
    chain_position: 1,
    prev_hash: '0'.repeat(64),
    this_hash: 'a'.repeat(64),
    occurred_at: '2026-05-21T12:00:00Z',
    actor_type: 'user',
    actor_id: 'u1',
    actor_email: 'alice@example.com',
    action_verb: 'created',
    resource_type: 'supplier',
    resource_id: 's1',
    request_id: null,
    ip_address: null,
    user_agent: null,
    before_redacted: null,
    after_redacted: null,
    metadata: null,
    ...overrides,
  } as AuditLogRead;
}

describe('AuditTimeline', () => {
  it('renders an empty-state message when there are no rows', () => {
    render(
      <MemoryRouter>
        <AuditTimeline items={[]} emptyMessage="Nothing here yet." />
      </MemoryRouter>,
    );
    expect(screen.getByText(/nothing here yet/i)).toBeInTheDocument();
    expect(screen.queryByTestId('audit-timeline')).toBeNull();
  });

  it('renders one entry per row with actor, verb and resource', () => {
    const items = [
      row({ id: 'r1', action_verb: 'created', actor_email: 'alice@example.com' }),
      row({
        id: 'r2',
        chain_position: 2,
        actor_type: 'system',
        actor_email: null,
        actor_id: null,
        action_verb: 'updated',
        resource_type: 'submission',
        resource_id: 'sub1',
      }),
    ];
    render(
      <MemoryRouter>
        <AuditTimeline items={items} />
      </MemoryRouter>,
    );
    const list = screen.getByTestId('audit-timeline');
    expect(list.querySelectorAll('li')).toHaveLength(2);
    expect(screen.getByText('alice@example.com')).toBeInTheDocument();
    expect(screen.getByText('system')).toBeInTheDocument();
    expect(screen.getByText('created')).toBeInTheDocument();
    expect(screen.getByText('updated')).toBeInTheDocument();
    expect(screen.getByText('supplier/s1')).toBeInTheDocument();
    expect(screen.getByText('submission/sub1')).toBeInTheDocument();
    // Each row links to its detail page.
    const links = list.querySelectorAll('a');
    expect(links[0].getAttribute('href')).toBe('/audit/r1');
    expect(links[1].getAttribute('href')).toBe('/audit/r2');
  });
});
