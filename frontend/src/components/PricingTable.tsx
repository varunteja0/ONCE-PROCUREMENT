import { Check } from 'lucide-react';
import { formatMoneyCents, type PricingTable as PricingTableData } from '@/services/billingApi';

interface PricingTableProps {
  data: PricingTableData;
  ctaLabel: string;
  onCtaClick: () => void;
  ctaDisabled?: boolean;
  ctaLoading?: boolean;
}

export function PricingTable({
  data,
  ctaLabel,
  onCtaClick,
  ctaDisabled = false,
  ctaLoading = false,
}: PricingTableProps): JSX.Element {
  const setup = data.prices.find((p) => p.key === 'setup');
  const monthly = data.prices.find((p) => p.key === 'monthly');
  return (
    <section
      aria-labelledby="pricing-plan-heading"
      className="mx-auto max-w-xl rounded-2xl border border-slate-200 bg-white p-8 shadow-sm"
    >
      <div className="text-center">
        <span className="inline-block rounded-full bg-indigo-50 px-3 py-1 text-xs font-medium uppercase tracking-wide text-indigo-700">
          Featured
        </span>
        <h2
          id="pricing-plan-heading"
          className="mt-3 text-2xl font-semibold text-slate-900"
        >
          {data.plan_name}
        </h2>
        <p className="mt-1 text-sm text-slate-600">{data.plan_tagline}</p>
      </div>

      <dl className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
        {setup ? (
          <div className="rounded-xl bg-slate-50 p-4 text-center">
            <dt className="text-xs font-medium uppercase text-slate-500">
              {setup.label}
            </dt>
            <dd
              className="mt-1 text-2xl font-semibold text-slate-900"
              aria-label={`Setup fee ${formatMoneyCents(setup.amount_cents, setup.currency)}`}
            >
              {formatMoneyCents(setup.amount_cents, setup.currency)}
            </dd>
            <p className="mt-1 text-xs text-slate-500">{setup.description}</p>
          </div>
        ) : null}
        {monthly ? (
          <div className="rounded-xl bg-slate-50 p-4 text-center">
            <dt className="text-xs font-medium uppercase text-slate-500">
              {monthly.label}
            </dt>
            <dd
              className="mt-1 text-2xl font-semibold text-slate-900"
              aria-label={`Monthly price ${formatMoneyCents(monthly.amount_cents, monthly.currency)} per month`}
            >
              {formatMoneyCents(monthly.amount_cents, monthly.currency)}
              <span className="text-sm font-normal text-slate-500">/mo</span>
            </dd>
            <p className="mt-1 text-xs text-slate-500">{monthly.description}</p>
          </div>
        ) : null}
      </dl>

      {data.features.length > 0 ? (
        <ul className="mt-6 space-y-2" aria-label="Plan features">
          {data.features.map((f) => (
            <li key={f} className="flex items-start gap-2 text-sm text-slate-700">
              <Check
                aria-hidden="true"
                className="mt-0.5 h-4 w-4 flex-none text-emerald-600"
              />
              <span>{f}</span>
            </li>
          ))}
        </ul>
      ) : null}

      <button
        type="button"
        onClick={onCtaClick}
        disabled={ctaDisabled || ctaLoading}
        className="mt-6 inline-flex w-full items-center justify-center rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {ctaLoading ? 'Loading…' : ctaLabel}
      </button>
    </section>
  );
}

export default PricingTable;
