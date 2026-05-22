import { type ReactElement, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, type MemoryRouterProps } from 'react-router-dom';
import { render, type RenderOptions, type RenderResult } from '@testing-library/react';

export interface RenderWithProvidersOptions extends Omit<RenderOptions, 'wrapper'> {
  routerProps?: MemoryRouterProps;
  queryClient?: QueryClient;
}

export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: Infinity, staleTime: Infinity },
      mutations: { retry: false },
    },
  });
}

export function renderWithProviders(
  ui: ReactElement,
  options: RenderWithProvidersOptions = {},
): RenderResult & { queryClient: QueryClient } {
  const queryClient = options.queryClient ?? createTestQueryClient();
  const Wrapper = ({ children }: { children: ReactNode }): JSX.Element => (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter {...options.routerProps}>{children}</MemoryRouter>
    </QueryClientProvider>
  );
  const result = render(ui, { ...options, wrapper: Wrapper });
  return Object.assign(result, { queryClient });
}

export * from '@testing-library/react';
export { default as userEvent } from '@testing-library/user-event';
