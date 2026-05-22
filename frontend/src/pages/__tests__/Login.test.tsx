import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

const login = vi.fn().mockResolvedValue(undefined);
vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({
    login,
    register: vi.fn(),
    logout: vi.fn(),
    user: null,
    isAuthenticated: false,
    isLoading: false,
  }),
}));
vi.mock('@/lib/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
  default: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));

import Login from '@/pages/Login';

function renderLogin(): void {
  render(
    <MemoryRouter>
      <Login />
    </MemoryRouter>,
  );
}

describe('Login page', () => {
  it('renders heading and inputs', () => {
    renderLogin();
    expect(screen.getByRole('heading', { name: /sign in to once/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it('shows validation errors when submitting empty form', async () => {
    renderLogin();
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));
    const alerts = await screen.findAllByRole('alert');
    expect(alerts.length).toBeGreaterThanOrEqual(1);
    expect(login).not.toHaveBeenCalled();
  });

  it('calls login with credentials on valid submit', async () => {
    renderLogin();
    await userEvent.type(screen.getByLabelText(/email/i), 'jane@example.com');
    await userEvent.type(screen.getByLabelText(/password/i), 'longpassword');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));
    await waitFor(() =>
      expect(login).toHaveBeenCalledWith({
        email: 'jane@example.com',
        password: 'longpassword',
      }),
    );
  });
});
