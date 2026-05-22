import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';
import {
  createCheckout,
  createPortal,
  getPricing,
  getSubscription,
  listInvoices,
  type CheckoutResponse,
  type InvoiceListResponse,
  type PortalResponse,
  type PricingTable,
  type SubscriptionRead,
} from '@/services/billingApi';

export const billingKeys = {
  all: ['billing'] as const,
  pricing: () => ['billing', 'pricing'] as const,
  subscription: () => ['billing', 'subscription'] as const,
  invoices: (params: { limit: number; offset: number }) =>
    ['billing', 'invoices', params] as const,
};

export function usePricing(): UseQueryResult<PricingTable, Error> {
  return useQuery({
    queryKey: billingKeys.pricing(),
    queryFn: getPricing,
    staleTime: 5 * 60 * 1000,
  });
}

export function useSubscription(
  enabled = true,
): UseQueryResult<SubscriptionRead | null, Error> {
  return useQuery({
    queryKey: billingKeys.subscription(),
    queryFn: getSubscription,
    enabled,
  });
}

export function useInvoices(
  params: { limit?: number; offset?: number } = {},
): UseQueryResult<InvoiceListResponse, Error> {
  const limit = params.limit ?? 25;
  const offset = params.offset ?? 0;
  return useQuery({
    queryKey: billingKeys.invoices({ limit, offset }),
    queryFn: () => listInvoices({ limit, offset }),
  });
}

export function useCreateCheckout(): UseMutationResult<
  CheckoutResponse,
  Error,
  void
> {
  return useMutation({
    mutationFn: () => createCheckout('starter'),
  });
}

export function useOpenPortal(): UseMutationResult<
  PortalResponse,
  Error,
  void
> {
  return useMutation({
    mutationFn: () => createPortal(),
  });
}

export function useInvalidateBilling(): () => void {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: billingKeys.all });
  };
}
