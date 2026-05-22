// --- L3.9 inbound ---
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';
import {
  inboundApi,
  type InboundEmailDetail,
  type InboundEmailListItem,
  type InboundRetryResponse,
  type InboundRule,
  type InboundRuleCreate,
  type InboundRuleUpdate,
  type InboundStatus,
} from '@/services/inboundApi';

export const inboundKeys = {
  all: ['inbound'] as const,
  list: (status?: InboundStatus) => ['inbound', 'list', status ?? 'all'] as const,
  detail: (id: string) => ['inbound', 'detail', id] as const,
  rules: ['inbound', 'rules'] as const,
};

export function useInboundList(
  status?: InboundStatus,
  options: { refetchInterval?: number | false } = {},
): UseQueryResult<InboundEmailListItem[], Error> {
  return useQuery({
    queryKey: inboundKeys.list(status),
    queryFn: () => inboundApi.list({ limit: 100, status }),
    refetchInterval: options.refetchInterval ?? 10_000,
  });
}

export function useInboundEmail(
  id: string | undefined,
): UseQueryResult<InboundEmailDetail, Error> {
  return useQuery({
    queryKey: id ? inboundKeys.detail(id) : (['inbound', 'detail', 'noop'] as const),
    enabled: Boolean(id),
    queryFn: () => inboundApi.get(id as string),
  });
}

export function useRetryInbound(): UseMutationResult<
  InboundRetryResponse,
  Error,
  string
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => inboundApi.retry(id),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: inboundKeys.detail(id) });
      qc.invalidateQueries({ queryKey: ['inbound', 'list'] });
    },
  });
}

export function useQuarantineInbound(): UseMutationResult<
  InboundRetryResponse,
  Error,
  string
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => inboundApi.quarantine(id),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: inboundKeys.detail(id) });
      qc.invalidateQueries({ queryKey: ['inbound', 'list'] });
    },
  });
}

export function useInboundRules(): UseQueryResult<InboundRule[], Error> {
  return useQuery({
    queryKey: inboundKeys.rules,
    queryFn: () => inboundApi.listRules(),
  });
}

export function useCreateInboundRule(): UseMutationResult<
  InboundRule,
  Error,
  InboundRuleCreate
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body) => inboundApi.createRule(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: inboundKeys.rules }),
  });
}

export function useUpdateInboundRule(): UseMutationResult<
  InboundRule,
  Error,
  { id: string; body: InboundRuleUpdate }
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }) => inboundApi.updateRule(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: inboundKeys.rules }),
  });
}

export function useDeleteInboundRule(): UseMutationResult<void, Error, string> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => inboundApi.deleteRule(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: inboundKeys.rules }),
  });
}

export function useReorderInboundRules(): UseMutationResult<
  InboundRule[],
  Error,
  string[]
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (order: string[]) => inboundApi.reorderRules(order),
    onSuccess: () => qc.invalidateQueries({ queryKey: inboundKeys.rules }),
  });
}
