import { describe, expect, it, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ProtectedRoute from '@/components/ProtectedRoute';
import { useAuthStore } from '@/store/auth';

function Tree(): JSX.Element {
  return (
    <Routes>
      <Route path="/login" element={<div>login page</div>} />
      <Route
        path="/secret"
        element={
          <ProtectedRoute>
            <div>secret content</div>
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}

describe('ProtectedRoute', () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: null,
      tenantId: null,
      isAuthenticated: false,
    });
  });

  it('redirects unauthenticated users to /login', () => {
    render(
      <MemoryRouter initialEntries={['/secret']}>
        <Tree />
      </MemoryRouter>,
    );
    expect(screen.getByText('login page')).toBeInTheDocument();
    expect(screen.queryByText('secret content')).toBeNull();
  });

  it('renders children when authenticated', () => {
    useAuthStore.setState({
      user: {
        id: 'u1',
        email: 'x@y.z',
        tenant_id: 't1',
        role: 'admin',
      } as never,
      tenantId: 't1',
      isAuthenticated: true,
    });
    render(
      <MemoryRouter initialEntries={['/secret']}>
        <Tree />
      </MemoryRouter>,
    );
    expect(screen.getByText('secret content')).toBeInTheDocument();
  });
});
