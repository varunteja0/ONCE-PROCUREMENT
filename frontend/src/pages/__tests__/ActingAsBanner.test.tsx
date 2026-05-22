import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

const switchActAs = vi.fn().mockResolvedValue(null);
vi.mock('@/hooks/useCockpit', () => ({
  useCockpit: () => ({
    operator: null,
    isAuthenticated: true,
    actingAsTenantId: 't-acme',
    login: vi.fn(),
    logout: vi.fn(),
    refreshMe: vi.fn(),
    switchActAs,
  }),
  useCockpitTenants: () => ({
    data: {
      items: [
        {
          id: 't-acme',
          name: 'Acme Insurance',
          slug: 'acme',
          plan: 'pilot',
          is_active: true,
          created_at: '2026-05-21T00:00:00Z',
          supplier_count: 0,
          submission_count: 0,
          last_activity_at: null,
        },
      ],
      total: 1,
    },
    isLoading: false,
  }),
  useCockpitAudit: () => ({ data: undefined, isLoading: false }),
}));

import ActingAsBanner from '@/components/ActingAsBanner';

describe('ActingAsBanner', () => {
  it('renders the acting-as tenant label', () => {
    render(
      <MemoryRouter>
        <ActingAsBanner />
      </MemoryRouter>,
    );
    expect(screen.getByTestId('acting-as-banner')).toBeInTheDocument();
    expect(screen.getByText(/acme insurance/i)).toBeInTheDocument();
    expect(screen.getByText(/acting as tenant/i)).toBeInTheDocument();
  });

  it('clears the actingAs state when Exit tenant is clicked', async () => {
    render(
      <MemoryRouter>
        <ActingAsBanner />
      </MemoryRouter>,
    );
    await userEvent.click(
      screen.getByRole('button', { name: /exit tenant context/i }),
    );
    expect(switchActAs).toHaveBeenCalledWith(null);
  });
});

describe('ActingAsBanner when not acting', () => {
  it('renders nothing when actingAsTenantId is null', async () => {
    // Re-mock for this test
    vi.resetModules();
    vi.doMock('@/hooks/useCockpit', () => ({
      useCockpit: () => ({
        operator: null,
        isAuthenticated: true,
        actingAsTenantId: null,
        login: vi.fn(),
        logout: vi.fn(),
        refreshMe: vi.fn(),
        switchActAs: vi.fn(),
      }),
      useCockpitTenants: () => ({ data: undefined, isLoading: false }),
      useCockpitAudit: () => ({ data: undefined, isLoading: false }),
    }));
    const { default: Banner } = await import('@/components/ActingAsBanner');
    const { container } = render(
      <MemoryRouter>
        <Banner />
      </MemoryRouter>,
    );
    expect(container.firstChild).toBeNull();
  });
});
