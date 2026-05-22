import { ExternalLink, Loader2 } from 'lucide-react';
import SubscriptionBadge from '@/components/SubscriptionBadge';
import {
  useInvoices,
  useOpenPortal,
  useSubscription,
  useCreateCheckout,
} from '@/hooks/useBilling';
import { formatMoneyCents } from '@/services/billingApi';
import { extractErrorMessage } from '@/services/api';
import toast from '@/lib/toast';

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString();
  } catch {
    return iso;
  }
}

export default function Billing(): JSX.Element {
  const sub = useSubscription();
  const invoices = useInvoices({ limit: 25 });
  const openPortal = useOpenPortal();
  const checkout = useCreateCheckout();

  const hasSubscription = Boolean(sub.data);

  async function onPortal(): Promise<void> {
    try {
      const resp = await openPortal.mutateAsync();
      window.location.assign(resp.portal_url);
    } catch (err) {
      toast.error(
        extractErrorMessage(err, 'Could not open Stripe billing portal'),
      );
    }
  }

  async function onSubscribe(): Promise<void> {
    try {
      const resp = await checkout.mutateAsync();
      window.location.assign(resp.checkout_url);
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Could not start checkout'));
    }
  }

  return (
    <div className="space-y-8 p-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Billing</h1>
          <p className="text-sm text-slate-500">
            Manage your subscription, invoices, and payment method.
          </p>
        </div>
        <SubscriptionBadge status={sub.data?.status} />
      </header>

      <section
        aria-labelledby="subscription-heading"
        className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
      >
        <h2 id="subscription-heading" className="text-lg font-semibold">
          Subscription
        </h2>
        {sub.isLoading ? (
          <p className="mt-2 text-sm text-slate-500" role="status">
            Loading subscription…
          </p>
        ) : sub.data ? (
          <dl className="mt-4 grid grid-cols-1 gap-4 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-xs uppercase text-slate-500">Status</dt>
              <dd className="mt-1">
                <SubscriptionBadge status={sub.data.status} />
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-slate-500">Monthly price</dt>
              <dd className="mt-1 font-medium text-slate-900">
                {formatMoneyCents(sub.data.monthly_price_cents)}/mo
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-slate-500">
                Current period ends
              </dt>
              <dd className="mt-1 text-slate-900">
                {formatDate(sub.data.current_period_end)}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-slate-500">
                Setup fee paid
              </dt>
              <dd className="mt-1 text-slate-900">
                {sub.data.plan_setup_paid ? 'Yes' : 'No'}
              </dd>
            </div>
          </dl>
        ) : (
          <div className="mt-4 space-y-3">
            <p className="text-sm text-slate-600">
              You don&apos;t have an active subscription yet.
            </p>
            <button
              type="button"
              onClick={() => void onSubscribe()}
              disabled={checkout.isPending}
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
            >
              {checkout.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : null}
              Subscribe to Starter
            </button>
          </div>
        )}

        {hasSubscription ? (
          <div className="mt-6 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => void onPortal()}
              disabled={openPortal.isPending}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 shadow-sm hover:bg-slate-50 disabled:opacity-60"
            >
              {openPortal.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <ExternalLink className="h-4 w-4" />
              )}
              Manage in Stripe
            </button>
          </div>
        ) : null}
      </section>

      <section
        aria-labelledby="invoices-heading"
        className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
      >
        <h2 id="invoices-heading" className="text-lg font-semibold">
          Invoices
        </h2>
        {invoices.isLoading ? (
          <p className="mt-2 text-sm text-slate-500" role="status">
            Loading invoices…
          </p>
        ) : invoices.data && invoices.data.items.length > 0 ? (
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="py-2 pr-4">Date</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4 text-right">Amount</th>
                  <th className="py-2 pr-4" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {invoices.data.items.map((inv) => (
                  <tr key={inv.id}>
                    <td className="py-2 pr-4 text-slate-700">
                      {formatDate(inv.created_at)}
                    </td>
                    <td className="py-2 pr-4 capitalize text-slate-700">
                      {inv.status}
                    </td>
                    <td className="py-2 pr-4 text-right font-medium text-slate-900">
                      {formatMoneyCents(inv.amount_due_cents, inv.currency)}
                    </td>
                    <td className="py-2 pr-4 text-right">
                      {inv.hosted_invoice_url ? (
                        <a
                          className="text-indigo-600 hover:underline"
                          href={inv.hosted_invoice_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          View
                        </a>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="mt-2 text-sm text-slate-500">No invoices yet.</p>
        )}
      </section>
    </div>
  );
}
