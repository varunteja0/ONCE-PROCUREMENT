import { create } from 'zustand';
import {
  COCKPIT_ACTING_AS_KEY,
  COCKPIT_OPERATOR_KEY,
  cockpitTokenStorage,
  type OperatorMe,
  type OperatorTokenPair,
} from '@/services/cockpitApi';

function loadOperator(): OperatorMe | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(COCKPIT_OPERATOR_KEY);
    return raw ? (JSON.parse(raw) as OperatorMe) : null;
  } catch {
    return null;
  }
}

function persistOperator(op: OperatorMe | null): void {
  if (typeof window === 'undefined') return;
  try {
    if (op) {
      window.localStorage.setItem(COCKPIT_OPERATOR_KEY, JSON.stringify(op));
    } else {
      window.localStorage.removeItem(COCKPIT_OPERATOR_KEY);
    }
  } catch {
    /* ignore */
  }
}

function loadActingAs(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage.getItem(COCKPIT_ACTING_AS_KEY);
  } catch {
    return null;
  }
}

function persistActingAs(tenantId: string | null): void {
  if (typeof window === 'undefined') return;
  try {
    if (tenantId) {
      window.localStorage.setItem(COCKPIT_ACTING_AS_KEY, tenantId);
    } else {
      window.localStorage.removeItem(COCKPIT_ACTING_AS_KEY);
    }
  } catch {
    /* ignore */
  }
}

export interface CockpitState {
  /** @deprecated Source of truth is `useCockpit().operator` (TanStack Query).
   *  Kept populated by the Query layer for back-compat with route guards. */
  operator: OperatorMe | null;
  actingAsTenantId: string | null;
  isAuthenticated: boolean;
  /** @deprecated Use `useCockpit().login`; back-compat shim. */
  setSession: (operator: OperatorMe, tokens?: OperatorTokenPair) => void;
  /** @deprecated Use `useCockpit().refreshMe`; back-compat shim. */
  setOperator: (operator: OperatorMe) => void;
  setActingAs: (tenantId: string | null) => void;
  clear: () => void;
  hydrate: () => void;
}

const initialOperator = loadOperator();
const initialActingAs = loadActingAs();
const initialAuthenticated =
  initialOperator !== null && cockpitTokenStorage.getAccess() !== null;

export const useCockpitStore = create<CockpitState>((set) => ({
  operator: initialOperator,
  actingAsTenantId: initialActingAs,
  isAuthenticated: initialAuthenticated,
  setSession: (operator, tokens) => {
    if (tokens) cockpitTokenStorage.setPair(tokens);
    persistOperator(operator);
    set({ operator, isAuthenticated: true });
  },
  setOperator: (operator) => {
    persistOperator(operator);
    set({ operator, isAuthenticated: true });
  },
  setActingAs: (tenantId) => {
    persistActingAs(tenantId);
    set({ actingAsTenantId: tenantId });
  },
  clear: () => {
    cockpitTokenStorage.clear();
    persistOperator(null);
    persistActingAs(null);
    set({ operator: null, actingAsTenantId: null, isAuthenticated: false });
  },
  hydrate: () => {
    const operator = loadOperator();
    const actingAs = loadActingAs();
    set({
      operator,
      actingAsTenantId: actingAs,
      isAuthenticated:
        operator !== null && cockpitTokenStorage.getAccess() !== null,
    });
  },
}));
