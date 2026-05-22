import { Navigate, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { useCockpitStore } from '@/store/cockpitStore';

export interface CockpitProtectedRouteProps {
  children: ReactNode;
}

export default function CockpitProtectedRoute({
  children,
}: CockpitProtectedRouteProps): JSX.Element {
  const isAuthenticated = useCockpitStore((s) => s.isAuthenticated);
  const location = useLocation();

  if (!isAuthenticated) {
    return (
      <Navigate
        to="/cockpit/login"
        replace
        state={{ from: `${location.pathname}${location.search}` }}
      />
    );
  }
  return <>{children}</>;
}
