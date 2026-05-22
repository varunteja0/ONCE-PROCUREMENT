import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';
import type { CrudClient, CrudParams } from '@/api/crud';
import type { PagedResponse } from '@/types/api';

/**
 * Generic React-Query bindings for any resource exposed via `createCrudClient`.
 *
 * Usage:
 *   const { useList, useOne, useCreate, useUpdate, useDelete } =
 *     buildCrudHooks(coisApi, 'cois');
 */
export interface CrudHooks<T, TCreate> {
  keys: {
    all: readonly ['crud', string];
    list: (params: CrudParams) => readonly ['crud', string, 'list', CrudParams];
    detail: (id: string) => readonly ['crud', string, 'detail', string];
  };
  useList: (
    params?: CrudParams,
    options?: { enabled?: boolean },
  ) => UseQueryResult<PagedResponse<T>, Error>;
  useOne: (
    id: string | undefined,
  ) => UseQueryResult<T, Error>;
  useCreate: () => UseMutationResult<T, Error, TCreate>;
  useUpdate: () => UseMutationResult<
    T,
    Error,
    { id: string; patch: Partial<TCreate> }
  >;
  useDelete: () => UseMutationResult<void, Error, string>;
}

export function buildCrudHooks<T, TCreate>(
  client: CrudClient<T, TCreate>,
  resource: string,
): CrudHooks<T, TCreate> {
  const keys = {
    all: ['crud', resource] as const,
    list: (params: CrudParams) =>
      ['crud', resource, 'list', params] as const,
    detail: (id: string) => ['crud', resource, 'detail', id] as const,
  };

  function useList(
    params: CrudParams = {},
    options: { enabled?: boolean } = {},
  ): UseQueryResult<PagedResponse<T>, Error> {
    return useQuery({
      queryKey: keys.list(params),
      queryFn: () => client.list(params),
      enabled: options.enabled ?? true,
    });
  }

  function useOne(id: string | undefined): UseQueryResult<T, Error> {
    return useQuery({
      queryKey: id ? keys.detail(id) : (['crud', resource, 'detail', 'noop'] as const),
      enabled: Boolean(id),
      queryFn: () => client.get(id ?? ''),
    });
  }

  function useCreate(): UseMutationResult<T, Error, TCreate> {
    const qc = useQueryClient();
    return useMutation({
      mutationFn: (input: TCreate) => client.create(input),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: keys.all });
      },
    });
  }

  function useUpdate(): UseMutationResult<
    T,
    Error,
    { id: string; patch: Partial<TCreate> }
  > {
    const qc = useQueryClient();
    return useMutation({
      mutationFn: ({ id, patch }) => client.update(id, patch),
      onSuccess: (data, vars) => {
        qc.invalidateQueries({ queryKey: keys.all });
        qc.setQueryData(keys.detail(vars.id), data);
      },
    });
  }

  function useDelete(): UseMutationResult<void, Error, string> {
    const qc = useQueryClient();
    return useMutation({
      mutationFn: (id: string) => client.remove(id),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: keys.all });
      },
    });
  }

  return { keys, useList, useOne, useCreate, useUpdate, useDelete };
}
