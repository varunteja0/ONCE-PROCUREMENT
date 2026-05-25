import { useNavigate } from 'react-router-dom';
import PricingTable from '@/components/PricingTable';
import { usePricing, useCreateCheckout } from '@/hooks/useBilling';
import { tokenStorage, extractErrorMessage } from '@/services/api';
import toast from '@/lib/toast';
import { sanitizeRedirect } from '@/lib/security';

export default function Pricing(): JSX.Element {
  const navigate = useNavigate();
  const { data, isLoading, isError, error, refetch } = usePricing();
  const checkout = useCreateCheckout();

  const isAuthed = Boolean(tokenStorage.getAccess());

  async function onCta(): Promise<void> {
    if (!isAuthed) {
      const next = sanitizeRedirect('/billing');
      navigate(`/login?next=${encodeURIComponent(next)}`);
      return;
    }
    try {
      const resp = await checkout.mutateAsync();
      window.location.assign(resp.checkout_url);
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Unable to start checkout'));
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-12">
      <div className="mx-auto max-w-3xl">
        <header className="text-center">
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">
            Pricing
          </h1>
          <p className="mt-2 text-sm text-slate-600">
            Submit once. Prove it forever. Simple, transparent pricing.
          </p>
        </header>

        <div className="mt-10">
          {isLoading ? (
            <p
              className="text-center text-sm text-slate-500"
              role="status"
              aria-live="polite"
            >
              Loading pricing…
            </p>
          ) : null}
          {isError ? (
            <div
              role="alert"
              className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800"
            >
              <p>Failed to load pricing: {error?.message ?? 'unknown error'}</p>
              <button
                type="button"
                onClick={() => void refetch()}
                className="mt-2 text-sm font-medium text-rose-700 underline"
              >
                Retry
              </button>
            </div>
          ) : null}
          {data ? (
            <PricingTable
              data={data}
              ctaLabel={isAuthed ? 'Start checkout' : 'Sign in to subscribe'}
              ctaLoading={checkout.isPending}
              onCtaClick={() => void onCta()}
            />
          ) : null}
        </div>
      </div>
    </main>
  );
}
