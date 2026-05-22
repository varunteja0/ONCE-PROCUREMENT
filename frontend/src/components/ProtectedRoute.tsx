import { Navigate, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { useAuthStore } from '@/store/auth';

export interface ProtectedRouteProps {
  children: ReactNode;
}

export default function ProtectedRoute({
  children,
}: ProtectedRouteProps): JSX.Element {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const location = useLocation();

  if (!isAuthenticated) {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: `${location.pathname}${location.search}` }}
      />
    );
  }
  return <>{children}</>;
}
