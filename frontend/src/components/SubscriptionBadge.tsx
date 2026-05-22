import type { SubscriptionStatusValue } from '@/services/billingApi';

interface SubscriptionBadgeProps {
  status: SubscriptionStatusValue | null | undefined;
}

const STYLES: Record<SubscriptionStatusValue, string> = {
  incomplete: 'bg-slate-100 text-slate-700 ring-slate-200',
  incomplete_expired: 'bg-slate-100 text-slate-700 ring-slate-200',
  trialing: 'bg-sky-50 text-sky-700 ring-sky-200',
  active: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  past_due: 'bg-amber-50 text-amber-800 ring-amber-200',
  canceled: 'bg-rose-50 text-rose-700 ring-rose-200',
  unpaid: 'bg-rose-50 text-rose-700 ring-rose-200',
  paused: 'bg-slate-100 text-slate-700 ring-slate-200',
};

const LABELS: Record<SubscriptionStatusValue, string> = {
  incomplete: 'Incomplete',
  incomplete_expired: 'Expired',
  trialing: 'Trialing',
  active: 'Active',
  past_due: 'Past due',
  canceled: 'Canceled',
  unpaid: 'Unpaid',
  paused: 'Paused',
};

export function SubscriptionBadge({
  status,
}: SubscriptionBadgeProps): JSX.Element {
  if (!status) {
    return (
      <span
        className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700 ring-1 ring-inset ring-slate-200"
        aria-label="Subscription status: none"
      >
        No subscription
      </span>
    );
  }
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${STYLES[status]}`}
      aria-label={`Subscription status: ${LABELS[status]}`}
    >
      {LABELS[status]}
    </span>
  );
}

export default SubscriptionBadge;
