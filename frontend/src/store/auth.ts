import type { TokenPair, UserMe } from "@/services/api";
import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY, tokenStorage } from "@/services/api";
import { create } from "zustand";

const USER_STORAGE_KEY = "once.user";

interface PersistedSession {
  user: UserMe | null;
  tenantId: string | null;
}

function loadPersistedSession(): PersistedSession {
  if (typeof window === "undefined") {
    return { user: null, tenantId: null };
  }
  try {
    const raw = window.localStorage.getItem(USER_STORAGE_KEY);
    if (!raw) return { user: null, tenantId: null };
    const parsed = JSON.parse(raw) as UserMe;
    return { user: parsed, tenantId: parsed.tenant_id };
  } catch {
    return { user: null, tenantId: null };
  }
}

function persistUser(user: UserMe | null): void {
  if (typeof window === "undefined") return;
  try {
    if (user) {
      window.localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
    } else {
      window.localStorage.removeItem(USER_STORAGE_KEY);
    }
  } catch {
    /* ignore */
  }
}

export interface AuthState {
  /** @deprecated Source of truth is `useAuth().user` (TanStack Query). Kept
   *  populated by the Query layer for back-compat with route guards. */
  user: UserMe | null;
  /** @deprecated Derived from `user.tenant_id`; kept for back-compat. */
  tenantId: string | null;
  isAuthenticated: boolean;
  setAuthenticated: (value: boolean) => void;
  /** @deprecated Use `useAuth().login`; this is now a back-compat shim. */
  setSession: (user: UserMe, tokens?: TokenPair) => void;
  /** @deprecated Use `useAuth().refreshMe`; back-compat shim. */
  setUser: (user: UserMe) => void;
  clearSession: () => void;
  hydrate: () => void;
}

const { user: initialUser, tenantId: initialTenantId } = loadPersistedSession();
const initialAuthenticated = initialUser !== null && tokenStorage.getAccess() !== null;

export const useAuthStore = create<AuthState>((set) => ({
  user: initialUser,
  tenantId: initialTenantId,
  isAuthenticated: initialAuthenticated,
  setAuthenticated: (value) => set({ isAuthenticated: value }),
  setSession: (user, tokens) => {
    if (tokens) tokenStorage.setPair(tokens);
    persistUser(user);
    set({ user, tenantId: user.tenant_id, isAuthenticated: true });
  },
  setUser: (user) => {
    persistUser(user);
    set({ user, tenantId: user.tenant_id, isAuthenticated: true });
  },
  clearSession: () => {
    tokenStorage.clear();
    persistUser(null);
    set({ user: null, tenantId: null, isAuthenticated: false });
  },
  hydrate: () => {
    const { user, tenantId } = loadPersistedSession();
    set({
      user,
      tenantId,
      isAuthenticated: user !== null && tokenStorage.getAccess() !== null,
    });
  },
}));

if (typeof window !== "undefined") {
  window.addEventListener("storage", (event) => {
    if (event.key === ACCESS_TOKEN_KEY || event.key === REFRESH_TOKEN_KEY || event.key === USER_STORAGE_KEY) {
      useAuthStore.getState().hydrate();
    }
  });
}
