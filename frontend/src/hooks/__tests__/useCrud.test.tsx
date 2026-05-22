import { describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { type ReactNode } from 'react';
import { buildCrudHooks } from '@/hooks/useCrud';
import type { CrudClient } from '@/api/crud';

interface Widget {
  id: string;
  name: string;
}
interface WidgetCreate {
  name: string;
}

function makeClient(): CrudClient<Widget, WidgetCreate> {
  return {
    list: vi.fn().mockResolvedValue({
      items: [{ id: '1', name: 'a' }],
      total: 1,
      limit: 50,
      offset: 0,
    }),
    get: vi.fn().mockResolvedValue({ id: '1', name: 'a' }),
    create: vi.fn().mockResolvedValue({ id: '2', name: 'b' }),
    update: vi.fn().mockResolvedValue({ id: '1', name: 'a2' }),
    remove: vi.fn().mockResolvedValue(undefined),
  };
}

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }): JSX.Element {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe('buildCrudHooks', () => {
  it('builds query keys', () => {
    const client = makeClient();
    const hooks = buildCrudHooks<Widget, WidgetCreate>(client, 'widgets');
    expect(hooks.keys.all).toEqual(['crud', 'widgets']);
    expect(hooks.keys.detail('1')).toEqual(['crud', 'widgets', 'detail', '1']);
    expect(hooks.keys.list({ limit: 10 })).toEqual([
      'crud',
      'widgets',
      'list',
      { limit: 10 },
    ]);
  });

  it('useList fetches via client.list', async () => {
    const client = makeClient();
    const hooks = buildCrudHooks<Widget, WidgetCreate>(client, 'widgets');
    const { result } = renderHook(() => hooks.useList({ limit: 10, offset: 0 }), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items).toHaveLength(1);
    expect(client.list).toHaveBeenCalledWith({ limit: 10, offset: 0 });
  });

  it('useOne is disabled without id', () => {
    const client = makeClient();
    const hooks = buildCrudHooks<Widget, WidgetCreate>(client, 'widgets');
    const { result } = renderHook(() => hooks.useOne(undefined), {
      wrapper: makeWrapper(),
    });
    expect(result.current.fetchStatus).toBe('idle');
    expect(client.get).not.toHaveBeenCalled();
  });

  it('useCreate invokes mutation', async () => {
    const client = makeClient();
    const hooks = buildCrudHooks<Widget, WidgetCreate>(client, 'widgets');
    const { result } = renderHook(() => hooks.useCreate(), {
      wrapper: makeWrapper(),
    });
    result.current.mutate({ name: 'b' });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.create).toHaveBeenCalledWith({ name: 'b' });
  });
});
