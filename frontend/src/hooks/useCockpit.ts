// React hooks for the cockpit surface: login / logout / current operator /
// act-as switching. Wraps the cockpit API + Zustand store so pages don't
// have to thread state by hand.
import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  cockpitActAs,
  cockpitListAudit,
  cockpitListTenants,
  cockpitLogin,
  cockpitLogout,
  cockpitMe,
  type CockpitAuditListResponse,
  type CockpitTenantListResponse,
  type OperatorLoginInput,
} from '@/services/cockpitApi';
import { useCockpitStore } from '@/store/cockpitStore';

export function useCockpit() {
  const operator = useCockpitStore((s) => s.operator);
  const isAuthenticated = useCockpitStore((s) => s.isAuthenticated);
  const actingAsTenantId = useCockpitStore((s) => s.actingAsTenantId);
  const setSession = useCockpitStore((s) => s.setSession);
  const setOperator = useCockpitStore((s) => s.setOperator);
  const setActingAs = useCockpitStore((s) => s.setActingAs);
  const clear = useCockpitStore((s) => s.clear);
  const navigate = useNavigate();

  const login = useCallback(
    async (input: OperatorLoginInput) => {
      const tokens = await cockpitLogin(input);
      const me = await cockpitMe();
      setSession(me, tokens);
      return me;
    },
    [setSession],
  );

  const logout = useCallback(async () => {
    await cockpitLogout();
    clear();
    navigate('/cockpit/login', { replace: true });
  }, [clear, navigate]);

  const refreshMe = useCallback(async () => {
    const me = await cockpitMe();
    setOperator(me);
    return me;
  }, [setOperator]);

  const switchActAs = useCallback(
    async (tenantId: string | null) => {
      if (tenantId === null) {
        setActingAs(null);
        return null;
      }
      const resp = await cockpitActAs(tenantId);
      setActingAs(resp.tenant_id);
      return resp;
    },
    [setActingAs],
  );

  return {
    operator,
    isAuthenticated,
    actingAsTenantId,
    login,
    logout,
    refreshMe,
    switchActAs,
  };
}

export function useCockpitTenants() {
  return useQuery<CockpitTenantListResponse>({
    queryKey: ['cockpit', 'tenants'],
    queryFn: cockpitListTenants,
  });
}

export function useCockpitAudit(params: {
  limit?: number;
  operator_id?: string;
  tenant_id?: string;
} = {}) {
  return useQuery<CockpitAuditListResponse>({
    queryKey: ['cockpit', 'audit', params],
    queryFn: () => cockpitListAudit(params),
  });
}
