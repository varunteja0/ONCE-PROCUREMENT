import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useIdleTimeout } from '@/lib/idle';
import { useAuthStore } from '@/store/auth';
import { toast } from '@/lib/toast';
import { tokenStorage } from '@/services/api';

/**
 * Logs the user out after the configured period of inactivity.
 * Mount once inside the authenticated layout.
 */
export function IdleGuard(): null {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const clearSession = useAuthStore((s) => s.clearSession);
  const navigate = useNavigate();

  const onIdle = useCallback((): void => {
    tokenStorage.clear();
    clearSession();
    toast.info('You were signed out due to inactivity.');
    navigate('/login', { replace: true });
  }, [clearSession, navigate]);

  useIdleTimeout(isAuthenticated, onIdle);
  return null;
}
