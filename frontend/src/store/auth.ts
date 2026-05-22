import { create } from 'zustand';
import {
  ACCESS_TOKEN_KEY,
  REFRESH_TOKEN_KEY,
  tokenStorage,
} from '@/services/api';
import type { TokenPair, UserMe } from '@/services/api';

const USER_STORAGE_KEY = 'once.user';

interface PersistedSession {
  user: UserMe | null;
  tenantId: string | null;
}

function loadPersistedSession(): PersistedSession {
  if (typeof window === 'undefined') {
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
  if (typeof window === 'undefined') return;
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
  user: UserMe | null;
  tenantId: string | null;
  isAuthenticated: boolean;
  setSession: (user: UserMe, tokens?: TokenPair) => void;
  setUser: (user: UserMe) => void;
  clearSession: () => void;
  hydrate: () => void;
}

const { user: initialUser, tenantId: initialTenantId } = loadPersistedSession();
const initialAuthenticated =
  initialUser !== null && tokenStorage.getAccess() !== null;

export const useAuthStore = create<AuthState>((set) => ({
  user: initialUser,
  tenantId: initialTenantId,
  isAuthenticated: initialAuthenticated,
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

if (typeof window !== 'undefined') {
  window.addEventListener('storage', (event) => {
    if (
      event.key === ACCESS_TOKEN_KEY ||
      event.key === REFRESH_TOKEN_KEY ||
      event.key === USER_STORAGE_KEY
    ) {
      useAuthStore.getState().hydrate();
    }
  });
}
