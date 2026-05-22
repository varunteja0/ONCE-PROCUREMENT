import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('@/hooks/useCockpit', () => ({
  useCockpit: () => ({
    operator: {
      id: 'op-1',
      email: 'founder@once.io',
      role: 'founder',
      status: 'active',
      mfa_required: false,
      last_login_at: null,
      created_at: '2026-05-21T00:00:00Z',
      accessible_tenant_ids: [],
      all_tenants: true,
    },
    isAuthenticated: true,
    actingAsTenantId: null,
    login: vi.fn(),
    logout: vi.fn(),
    refreshMe: vi.fn(),
    switchActAs: vi.fn(),
  }),
  useCockpitTenants: () => ({
    data: {
      items: [
        {
          id: 't1',
          name: 'Acme',
          slug: 'acme',
          plan: 'pilot',
          is_active: true,
          created_at: '2026-05-21T00:00:00Z',
          supplier_count: 3,
          submission_count: 7,
          last_activity_at: null,
        },
        {
          id: 't2',
          name: 'Beta',
          slug: 'beta',
          plan: 'pilot',
          is_active: false,
          created_at: '2026-05-21T00:00:00Z',
          supplier_count: 1,
          submission_count: 2,
          last_activity_at: null,
        },
      ],
      total: 2,
    },
    isLoading: false,
  }),
  useCockpitAudit: () => ({
    data: {
      items: [
        {
          id: 'a1',
          operator_id: 'op-1',
          tenant_id_acted_as: null,
          action: 'cockpit.login',
          resource_type: 'operator_session',
          resource_id: null,
          request_id: null,
          method: 'POST',
          path: '/cockpit/auth/login',
          status_code: 200,
          ip: null,
          user_agent: null,
          payload_redacted: null,
          occurred_at: '2026-05-21T00:00:00Z',
        },
      ],
      total: 1,
    },
    isLoading: false,
  }),
}));

import CockpitDashboard from '@/pages/cockpit/Dashboard';

describe('CockpitDashboard page', () => {
  it('renders aggregate stats from useCockpitTenants', () => {
    render(
      <MemoryRouter>
        <CockpitDashboard />
      </MemoryRouter>,
    );
    expect(screen.getByText(/welcome, founder/i)).toBeInTheDocument();
    expect(screen.getByText('Tenants')).toBeInTheDocument();
    // total tenants = 2, active = 1, submissions = 9
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('9')).toBeInTheDocument();
  });

  it('lists recent audit events', () => {
    render(
      <MemoryRouter>
        <CockpitDashboard />
      </MemoryRouter>,
    );
    expect(screen.getByText('cockpit.login')).toBeInTheDocument();
    expect(screen.getByText('/cockpit/auth/login')).toBeInTheDocument();
  });
});
