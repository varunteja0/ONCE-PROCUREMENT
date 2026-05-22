// --- L3.8 pdf extraction ---
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';
import {
  extractionsApi,
  type ExtractionAcceptInput,
  type ExtractionEnqueueInput,
  type ExtractionListResponse,
  type ExtractionRead,
  type ExtractionRejectInput,
  type ExtractionSourceType,
} from '@/services/extractionsApi';

export const extractionsKeys = {
  all: ['extractions'] as const,
  list: (documentType: ExtractionSourceType | undefined, limit: number, offset: number) =>
    ['extractions', 'list', documentType ?? null, limit, offset] as const,
  detail: (id: string) => ['extractions', 'detail', id] as const,
};

/** Treat a row as in-flight while the worker still owns it. */
function isInFlight(row: ExtractionRead | undefined): boolean {
  return Boolean(row && row.status === 'pending');
}

export function useExtractionsList(
  params: {
    documentType?: ExtractionSourceType;
    limit?: number;
    offset?: number;
    refetchInterval?: number | false;
  } = {},
): UseQueryResult<ExtractionListResponse, Error> {
  const limit = params.limit ?? 50;
  const offset = params.offset ?? 0;
  return useQuery({
    queryKey: extractionsKeys.list(params.documentType, limit, offset),
    queryFn: () =>
      extractionsApi.list({
        document_type: params.documentType,
        limit,
        offset,
      }),
    refetchInterval: params.refetchInterval ?? false,
  });
}

export function useExtraction(
  id: string | undefined,
  options: { refetchInterval?: number | false; pollWhilePending?: boolean } = {},
): UseQueryResult<ExtractionRead, Error> {
  const pollWhilePending = options.pollWhilePending ?? true;
  return useQuery({
    queryKey: id
      ? extractionsKeys.detail(id)
      : (['extractions', 'detail', 'noop'] as const),
    enabled: Boolean(id),
    queryFn: () => extractionsApi.get(id as string),
    refetchInterval: (query) => {
      if (options.refetchInterval !== undefined) return options.refetchInterval;
      if (pollWhilePending && isInFlight(query.state.data as ExtractionRead | undefined)) {
        return 2000;
      }
      return false;
    },
  });
}

export function useEnqueueExtraction(): UseMutationResult<
  ExtractionRead,
  Error,
  ExtractionEnqueueInput
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: ExtractionEnqueueInput) => extractionsApi.enqueue(input),
    onSuccess: (row) => {
      qc.invalidateQueries({ queryKey: extractionsKeys.all });
      qc.setQueryData(extractionsKeys.detail(row.id), row);
    },
  });
}

export function useAcceptExtraction(): UseMutationResult<
  ExtractionRead,
  Error,
  ExtractionAcceptInput
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: ExtractionAcceptInput) => extractionsApi.accept(input),
    onSuccess: (row) => {
      qc.invalidateQueries({ queryKey: extractionsKeys.all });
      qc.setQueryData(extractionsKeys.detail(row.id), row);
    },
  });
}

export function useRejectExtraction(): UseMutationResult<
  ExtractionRead,
  Error,
  ExtractionRejectInput
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: ExtractionRejectInput) => extractionsApi.reject(input),
    onSuccess: (row) => {
      qc.invalidateQueries({ queryKey: extractionsKeys.all });
      qc.setQueryData(extractionsKeys.detail(row.id), row);
    },
  });
}
// --- /L3.8 pdf extraction ---
