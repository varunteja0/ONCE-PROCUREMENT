/**
 * TanStack Query hooks for verifier API keys (Phase L6.1).
 */

import {
    issueVerifierKey,
    listVerifierKeys,
    revokeVerifierKey,
    type VerifierKey,
    type VerifierKeyCreateInput,
    type VerifierKeyIssued,
} from '@/api/verifierKeys';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

const KEY = ['verifier-keys'] as const;

export function useVerifierKeys(): ReturnType<
  typeof useQuery<VerifierKey[], Error>
> {
  return useQuery<VerifierKey[], Error>({
    queryKey: KEY,
    queryFn: listVerifierKeys,
  });
}

export function useIssueVerifierKey(): ReturnType<
  typeof useMutation<VerifierKeyIssued, Error, VerifierKeyCreateInput>
> {
  const qc = useQueryClient();
  return useMutation<VerifierKeyIssued, Error, VerifierKeyCreateInput>({
    mutationFn: issueVerifierKey,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEY });
    },
  });
}

export function useRevokeVerifierKey(): ReturnType<
  typeof useMutation<void, Error, string>
> {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: revokeVerifierKey,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEY });
    },
  });
}
