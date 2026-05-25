// React hooks for the cockpit surface: login / logout / current operator /
// act-as switching. Wraps the cockpit API + Zustand store so pages don't
// have to thread state by hand.
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
  type OperatorMe,
} from "@/services/cockpitApi";
import { useCockpitStore } from "@/store/cockpitStore";
import { useQuery } from "@tanstack/react-query";
import { useCallback } from "react";
import { useNavigate } from "react-router-dom";

export const cockpitKeys = {
  me: ["cockpit", "me"] as const,
  tenants: ["cockpit", "tenants"] as const,
  audit: (params: object) => ["cockpit", "audit", params] as const,
};

export function useCockpit() {
  const storeOperator = useCockpitStore((s) => s.operator);
  const isAuthenticated = useCockpitStore((s) => s.isAuthenticated);
  const actingAsTenantId = useCockpitStore((s) => s.actingAsTenantId);
  const setSession = useCockpitStore((s) => s.setSession);
  const setOperator = useCockpitStore((s) => s.setOperator);
  const setActingAs = useCockpitStore((s) => s.setActingAs);
  const clear = useCockpitStore((s) => s.clear);
  const navigate = useNavigate();

  // Server-state for the current operator. The legacy `operator` field on
  // the Zustand store is kept populated for out-of-boundary consumers
  // (CockpitLayout, ProtectedRoute, etc.), but TanStack Query is the
  // authoritative source going forward.
  const meQuery = useQuery<OperatorMe, Error>({
    queryKey: cockpitKeys.me,
    queryFn: async () => {
      const op = await cockpitMe();
      setOperator(op);
      return op;
    },
    enabled: isAuthenticated,
    staleTime: 60_000,
  });

  const operator: OperatorMe | null = meQuery.data ?? storeOperator;

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
    navigate("/cockpit/login", { replace: true });
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
    isLoading: meQuery.isLoading,
    login,
    logout,
    refreshMe,
    switchActAs,
  };
}

export function useCockpitTenants() {
  return useQuery<CockpitTenantListResponse>({
    queryKey: cockpitKeys.tenants,
    queryFn: cockpitListTenants,
  });
}

export function useCockpitAudit(
  params: {
    limit?: number;
    operator_id?: string;
    tenant_id?: string;
  } = {},
) {
  return useQuery<CockpitAuditListResponse>({
    queryKey: cockpitKeys.audit(params),
    queryFn: () => cockpitListAudit(params),
  });
}
