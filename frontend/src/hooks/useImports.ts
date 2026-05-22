// --- L3.7 imports ---
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';
import {
  importsApi,
  type ImportColumnsResponse,
  type ImportEntityType,
  type ImportJob,
  type ImportJobDetail,
  type ImportJobListItem,
  type ImportUploadInput,
} from '@/services/importsApi';

export const importsKeys = {
  all: ['imports'] as const,
  list: (limit: number, offset: number) =>
    ['imports', 'list', limit, offset] as const,
  detail: (id: string) => ['imports', 'detail', id] as const,
  columns: (entity: ImportEntityType) => ['imports', 'columns', entity] as const,
};

export function useImportsList(
  limit = 50,
  offset = 0,
  options: { refetchInterval?: number | false } = {},
): UseQueryResult<{ items: ImportJobListItem[]; total: number }, Error> {
  return useQuery({
    queryKey: importsKeys.list(limit, offset),
    queryFn: () => importsApi.list({ limit, offset }),
    refetchInterval: options.refetchInterval ?? false,
  });
}

export function useImport(
  id: string | undefined,
  options: { refetchInterval?: number | false } = {},
): UseQueryResult<ImportJobDetail, Error> {
  return useQuery({
    queryKey: id ? importsKeys.detail(id) : (['imports', 'detail', 'noop'] as const),
    enabled: Boolean(id),
    queryFn: () => importsApi.get(id ?? ''),
    refetchInterval: options.refetchInterval ?? false,
  });
}

export function useImportColumns(
  entity: ImportEntityType | undefined,
): UseQueryResult<ImportColumnsResponse, Error> {
  return useQuery({
    queryKey: entity
      ? importsKeys.columns(entity)
      : (['imports', 'columns', 'noop'] as const),
    enabled: Boolean(entity),
    queryFn: () => importsApi.columns(entity as ImportEntityType),
    staleTime: 5 * 60 * 1000,
  });
}

export function useUploadImport(): UseMutationResult<
  ImportJob,
  Error,
  ImportUploadInput
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: ImportUploadInput) => importsApi.upload(input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: importsKeys.all });
    },
  });
}

export function useCommitImport(): UseMutationResult<ImportJob, Error, string> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => importsApi.commit(id),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: importsKeys.all });
      qc.invalidateQueries({ queryKey: importsKeys.detail(id) });
    },
  });
}

export function useCancelImport(): UseMutationResult<ImportJob, Error, string> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => importsApi.cancel(id),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: importsKeys.all });
      qc.invalidateQueries({ queryKey: importsKeys.detail(id) });
    },
  });
}
// --- /L3.7 imports ---
