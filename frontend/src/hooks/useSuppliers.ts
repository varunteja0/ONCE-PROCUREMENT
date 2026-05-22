import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';
import { api } from '@/services/api';
import type {
  Supplier,
  SupplierCreateInput,
  SupplierListItem,
  SupplierUpdateInput,
} from '@/services/api';

export interface UseSuppliersParams {
  search?: string;
  page?: number;
  pageSize?: number;
}

const DEFAULT_PAGE_SIZE = 50;

export const suppliersKeys = {
  all: ['suppliers'] as const,
  list: (params: UseSuppliersParams) =>
    ['suppliers', 'list', params] as const,
  detail: (id: string) => ['suppliers', 'detail', id] as const,
};

export function useSuppliers(
  params: UseSuppliersParams = {},
): UseQueryResult<SupplierListItem[], Error> {
  const page = params.page ?? 1;
  const pageSize = params.pageSize ?? DEFAULT_PAGE_SIZE;
  return useQuery({
    queryKey: suppliersKeys.list({ ...params, page, pageSize }),
    queryFn: async () => {
      const resp = await api.get<SupplierListItem[]>('/suppliers', {
        params: {
          search: params.search,
          limit: pageSize,
          offset: (page - 1) * pageSize,
        },
      });
      return resp.data;
    },
  });
}

export function useSupplier(
  supplierId: string | undefined,
): UseQueryResult<Supplier, Error> {
  return useQuery({
    queryKey: supplierId
      ? suppliersKeys.detail(supplierId)
      : ['suppliers', 'detail', 'noop'],
    enabled: Boolean(supplierId),
    queryFn: async () => {
      const resp = await api.get<Supplier>(`/suppliers/${supplierId}`);
      return resp.data;
    },
  });
}

export function useCreateSupplier(): UseMutationResult<
  Supplier,
  Error,
  SupplierCreateInput
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: SupplierCreateInput) => {
      const resp = await api.post<Supplier>('/suppliers', input);
      return resp.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: suppliersKeys.all });
      queryClient.setQueryData(suppliersKeys.detail(data.id), data);
    },
  });
}

export interface UpdateSupplierInput {
  id: string;
  patch: SupplierUpdateInput;
}

export function useUpdateSupplier(): UseMutationResult<
  Supplier,
  Error,
  UpdateSupplierInput
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, patch }: UpdateSupplierInput) => {
      const resp = await api.patch<Supplier>(`/suppliers/${id}`, patch);
      return resp.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: suppliersKeys.all });
      queryClient.setQueryData(suppliersKeys.detail(data.id), data);
    },
  });
}

export function useDeleteSupplier(): UseMutationResult<void, Error, string> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (supplierId: string) => {
      await api.delete(`/suppliers/${supplierId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: suppliersKeys.all });
    },
  });
}
