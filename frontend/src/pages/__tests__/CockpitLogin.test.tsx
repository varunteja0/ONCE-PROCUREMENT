import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

const login = vi.fn().mockResolvedValue({ id: 'op-1', email: 'founder@once.io', role: 'founder' });
const logout = vi.fn();
vi.mock('@/hooks/useCockpit', () => ({
  useCockpit: () => ({
    operator: null,
    isAuthenticated: false,
    actingAsTenantId: null,
    login,
    logout,
    refreshMe: vi.fn(),
    switchActAs: vi.fn(),
  }),
  useCockpitTenants: () => ({ data: undefined, isLoading: false }),
  useCockpitAudit: () => ({ data: undefined, isLoading: false }),
}));
vi.mock('@/lib/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
  default: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));

import CockpitLogin from '@/pages/cockpit/Login';

function renderPage(): void {
  render(
    <MemoryRouter>
      <CockpitLogin />
    </MemoryRouter>,
  );
}

describe('CockpitLogin page', () => {
  it('renders the cockpit heading and inputs', () => {
    renderPage();
    expect(
      screen.getByRole('heading', { name: /founder cockpit/i }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/operator email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/totp/i)).toBeInTheDocument();
  });

  it('calls login on valid submit and forwards TOTP when provided', async () => {
    renderPage();
    await userEvent.type(
      screen.getByLabelText(/operator email/i),
      'founder@once.io',
    );
    await userEvent.type(screen.getByLabelText(/password/i), 'CorrectHorse9!');
    await userEvent.type(screen.getByLabelText(/totp/i), '123456');
    await userEvent.click(
      screen.getByRole('button', { name: /enter cockpit/i }),
    );
    await waitFor(() =>
      expect(login).toHaveBeenCalledWith({
        email: 'founder@once.io',
        password: 'CorrectHorse9!',
        totp_code: '123456',
      }),
    );
  });

  it('omits totp_code when the TOTP field is empty', async () => {
    login.mockClear();
    renderPage();
    await userEvent.type(
      screen.getByLabelText(/operator email/i),
      'founder@once.io',
    );
    await userEvent.type(screen.getByLabelText(/password/i), 'CorrectHorse9!');
    await userEvent.click(
      screen.getByRole('button', { name: /enter cockpit/i }),
    );
    await waitFor(() =>
      expect(login).toHaveBeenCalledWith({
        email: 'founder@once.io',
        password: 'CorrectHorse9!',
        totp_code: undefined,
      }),
    );
  });
});
