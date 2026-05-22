// --- L3.9 inbound ---
import type { InboundStatus } from '@/services/inboundApi';
import { cn } from '@/lib/cn';

const STATUS_CLASS: Record<InboundStatus, string> = {
  received: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200',
  parsing: 'bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-200',
  routed: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200',
  quarantined: 'bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200',
  routing_failed: 'bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-200',
  discarded: 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-200',
};

const STATUS_LABEL: Record<InboundStatus, string> = {
  received: 'Received',
  parsing: 'Parsing',
  routed: 'Routed',
  quarantined: 'Quarantined',
  routing_failed: 'Routing failed',
  discarded: 'Discarded',
};

export function RoutingResultBadge({
  status,
}: {
  status: InboundStatus;
}): JSX.Element {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
        STATUS_CLASS[status],
      )}
    >
      {STATUS_LABEL[status]}
    </span>
  );
}

export default RoutingResultBadge;
