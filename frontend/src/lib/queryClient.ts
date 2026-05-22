import { QueryClient } from '@tanstack/react-query';

/**
 * Singleton TanStack Query client tuned for an internal dashboard:
 * - 5s staleTime keeps lists snappy without hammering the backend.
 * - Mutations do NOT retry (idempotency is not universally guaranteed).
 * - No refetch-on-focus to avoid surprise refetches mid-edit.
 */
export const queryClient: QueryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 5_000,
      gcTime: 5 * 60_000,
    },
    mutations: {
      retry: 0,
    },
  },
});
