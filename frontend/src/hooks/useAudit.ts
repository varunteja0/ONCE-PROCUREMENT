// --- L3.10 audit ---
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';
import {
  auditApi,
  type AuditChainVerifyResult,
  type AuditExportCreate,
  type AuditExportListItem,
  type AuditExportRead,
  type AuditListParams,
  type AuditLogList,
  type AuditLogRead,
} from '@/services/auditApi';

export const auditKeys = {
  all: ['audit'] as const,
  list: (params: AuditListParams) => ['audit', 'list', params] as const,
  detail: (id: string) => ['audit', 'detail', id] as const,
  byResource: (rt: string, rid: string) =>
    ['audit', 'resource', rt, rid] as const,
  verify: ['audit', 'chain', 'verify'] as const,
  exports: ['audit', 'exports'] as const,
  exportDetail: (id: string) => ['audit', 'exports', id] as const,
};

export function useAuditList(
  params: AuditListParams = {},
): UseQueryResult<AuditLogList, Error> {
  return useQuery({
    queryKey: auditKeys.list(params),
    queryFn: () => auditApi.list(params),
  });
}

export function useAuditEntry(
  id: string | undefined,
): UseQueryResult<AuditLogRead, Error> {
  return useQuery({
    queryKey: id ? auditKeys.detail(id) : (['audit', 'detail', 'noop'] as const),
    enabled: Boolean(id),
    queryFn: () => auditApi.get(id as string),
  });
}

export function useAuditByResource(
  resourceType: string | undefined,
  resourceId: string | undefined,
): UseQueryResult<AuditLogList, Error> {
  return useQuery({
    queryKey:
      resourceType && resourceId
        ? auditKeys.byResource(resourceType, resourceId)
        : (['audit', 'resource', 'noop'] as const),
    enabled: Boolean(resourceType && resourceId),
    queryFn: () => auditApi.byResource(resourceType as string, resourceId as string),
  });
}

export function useChainVerification(
  options: { refetchInterval?: number | false } = {},
): UseQueryResult<AuditChainVerifyResult, Error> {
  return useQuery({
    queryKey: auditKeys.verify,
    queryFn: () => auditApi.verify(),
    refetchInterval: options.refetchInterval ?? 60_000,
    staleTime: 30_000,
  });
}

export function useAuditExports(
  options: { refetchInterval?: number | false } = {},
): UseQueryResult<AuditExportListItem[], Error> {
  return useQuery({
    queryKey: auditKeys.exports,
    queryFn: () => auditApi.listExports(),
    refetchInterval: options.refetchInterval ?? 5_000,
  });
}

export function useAuditExport(
  id: string | undefined,
): UseQueryResult<AuditExportRead, Error> {
  return useQuery({
    queryKey: id ? auditKeys.exportDetail(id) : (['audit', 'exports', 'noop'] as const),
    enabled: Boolean(id),
    queryFn: () => auditApi.getExport(id as string),
    refetchInterval: 5_000,
  });
}

export function useCreateAuditExport(): UseMutationResult<
  AuditExportRead,
  Error,
  AuditExportCreate
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body) => auditApi.createExport(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: auditKeys.exports }),
  });
}
