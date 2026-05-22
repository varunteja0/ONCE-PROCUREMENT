import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';
import { api } from '@/services/api';
import type {
  Receipt,
  Submission,
  SubmissionCreateInput,
  SubmissionListItem,
  SubmissionStatus,
} from '@/services/api';

const DEFAULT_PAGE_SIZE = 50;

export interface UseSubmissionsParams {
  status?: SubmissionStatus;
  supplierId?: string;
  portalId?: string;
  page?: number;
  pageSize?: number;
}

export interface SubmissionsPage {
  items: SubmissionListItem[];
  page: number;
  pageSize: number;
}

export const submissionsKeys = {
  all: ['submissions'] as const,
  list: (params: UseSubmissionsParams) =>
    ['submissions', 'list', params] as const,
  detail: (id: string) => ['submissions', 'detail', id] as const,
  receipt: (id: string) => ['submissions', 'receipt', id] as const,
};

export function useSubmissions(
  params: UseSubmissionsParams = {},
): UseQueryResult<SubmissionsPage, Error> {
  const page = params.page ?? 1;
  const pageSize = params.pageSize ?? DEFAULT_PAGE_SIZE;

  return useQuery({
    queryKey: submissionsKeys.list({ ...params, page, pageSize }),
    queryFn: async () => {
      const resp = await api.get<SubmissionListItem[]>('/submissions', {
        params: {
          status: params.status,
          supplier_id: params.supplierId,
          portal_id: params.portalId,
          limit: pageSize,
          offset: (page - 1) * pageSize,
        },
      });
      return { items: resp.data, page, pageSize } satisfies SubmissionsPage;
    },
  });
}

export function useSubmission(
  submissionId: string | undefined,
): UseQueryResult<Submission, Error> {
  return useQuery({
    queryKey: submissionId
      ? submissionsKeys.detail(submissionId)
      : ['submissions', 'detail', 'noop'],
    enabled: Boolean(submissionId),
    queryFn: async () => {
      const resp = await api.get<Submission>(`/submissions/${submissionId}`);
      return resp.data;
    },
  });
}

export function useSubmissionReceipt(
  submissionId: string | undefined,
): UseQueryResult<Receipt, Error> {
  return useQuery({
    queryKey: submissionId
      ? submissionsKeys.receipt(submissionId)
      : ['submissions', 'receipt', 'noop'],
    enabled: Boolean(submissionId),
    queryFn: async () => {
      const resp = await api.get<Receipt>(`/submissions/${submissionId}/receipt`);
      return resp.data;
    },
  });
}

export function useRetrySubmission(): UseMutationResult<
  Submission,
  Error,
  string
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (submissionId: string) => {
      const resp = await api.post<Submission>(
        `/submissions/${submissionId}/retry`,
      );
      return resp.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: submissionsKeys.all });
      queryClient.setQueryData(submissionsKeys.detail(data.id), data);
    },
  });
}

export function useCreateSubmission(): UseMutationResult<
  Submission,
  Error,
  SubmissionCreateInput
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: SubmissionCreateInput) => {
      const resp = await api.post<Submission>('/submissions', input);
      return resp.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: submissionsKeys.all });
    },
  });
}
