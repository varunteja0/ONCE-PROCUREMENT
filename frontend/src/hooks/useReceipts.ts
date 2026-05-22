import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import { api } from '@/services/api';
import type { Receipt } from '@/services/api';

export interface UseReceiptsParams {
  supplierId?: string;
  page?: number;
  pageSize?: number;
}

const DEFAULT_PAGE_SIZE = 50;

export const receiptsKeys = {
  all: ['receipts'] as const,
  list: (params: UseReceiptsParams) => ['receipts', 'list', params] as const,
  detail: (id: string) => ['receipts', 'detail', id] as const,
};

export function useReceipts(
  params: UseReceiptsParams = {},
): UseQueryResult<Receipt[], Error> {
  const page = params.page ?? 1;
  const pageSize = params.pageSize ?? DEFAULT_PAGE_SIZE;
  return useQuery({
    queryKey: receiptsKeys.list({ ...params, page, pageSize }),
    queryFn: async () => {
      const resp = await api.get<Receipt[]>('/receipts', {
        params: {
          supplier_id: params.supplierId,
          limit: pageSize,
          offset: (page - 1) * pageSize,
        },
      });
      return resp.data;
    },
  });
}

export function useReceipt(
  receiptId: string | undefined,
): UseQueryResult<Receipt, Error> {
  return useQuery({
    queryKey: receiptId
      ? receiptsKeys.detail(receiptId)
      : ['receipts', 'detail', 'noop'],
    enabled: Boolean(receiptId),
    queryFn: async () => {
      const resp = await api.get<Receipt>(`/receipts/${receiptId}`);
      return resp.data;
    },
  });
}
