import { useMemo } from 'react';
import { RefreshCw, Eye } from 'lucide-react';
import StatusPill from '@/components/StatusPill';
import EmptyState from '@/components/EmptyState';
import type { SubmissionListItem, SubmissionStatus } from '@/services/api';

export interface SubmissionTableRow extends SubmissionListItem {
  supplier_name?: string | null;
  portal_name?: string | null;
  submitted_at?: string | null;
}

export interface SubmissionTableProps {
  items: readonly SubmissionTableRow[];
  onRetry?: (id: string) => void;
  onSelect?: (id: string) => void;
  isRetrying?: (id: string) => boolean;
  className?: string;
}

const RETRYABLE: ReadonlySet<SubmissionStatus> = new Set<SubmissionStatus>([
  'failed',
  'blocked',
]);

function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString();
}

export default function SubmissionTable({
  items,
  onRetry,
  onSelect,
  isRetrying,
  className,
}: SubmissionTableProps): JSX.Element {
  const rows = useMemo(() => items, [items]);

  if (rows.length === 0) {
    return (
      <EmptyState
        title="No submissions yet"
        description="Submissions you queue to carrier portals will appear here with their lifecycle status and signed receipts."
      />
    );
  }

  return (
    <div
      className={[
        'overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm',
        className ?? '',
      ]
        .filter(Boolean)
        .join(' ')}
    >
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <caption className="sr-only">Submissions list</caption>
        <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-600">
          <tr>
            <th scope="col" className="px-4 py-3">
              Status
            </th>
            <th scope="col" className="px-4 py-3">
              Supplier
            </th>
            <th scope="col" className="px-4 py-3">
              Portal
            </th>
            <th scope="col" className="px-4 py-3">
              Submitted
            </th>
            <th scope="col" className="px-4 py-3 text-right">
              Attempts
            </th>
            <th scope="col" className="px-4 py-3 text-right">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {rows.map((row) => {
            const submittedAt =
              row.submitted_at ?? row.completed_at ?? row.created_at;
            const retrying = isRetrying ? isRetrying(row.id) : false;
            const canRetry = onRetry !== undefined && RETRYABLE.has(row.status);
            return (
              <tr key={row.id} className="hover:bg-slate-50">
                <td className="whitespace-nowrap px-4 py-3">
                  <StatusPill status={row.status} />
                </td>
                <td className="px-4 py-3 text-slate-900">
                  {row.supplier_name ?? (
                    <span className="font-mono text-xs text-slate-500">
                      {row.supplier_id}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-slate-700">
                  {row.portal_name ?? (
                    <span className="font-mono text-xs text-slate-500">
                      {row.portal_id}
                    </span>
                  )}
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                  {formatDate(submittedAt)}
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums text-slate-700">
                  {row.attempt_count}
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-right">
                  <div className="inline-flex items-center gap-2">
                    {onSelect ? (
                      <button
                        type="button"
                        onClick={() => onSelect(row.id)}
                        aria-label={`View submission ${row.id}`}
                        className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2"
                      >
                        <Eye aria-hidden="true" className="h-3.5 w-3.5" />
                        View
                      </button>
                    ) : null}
                    {canRetry ? (
                      <button
                        type="button"
                        onClick={() => onRetry?.(row.id)}
                        disabled={retrying}
                        aria-label={`Retry submission ${row.id}`}
                        className="inline-flex items-center gap-1 rounded-md border border-amber-300 bg-amber-50 px-2.5 py-1.5 text-xs font-medium text-amber-800 transition hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-60 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-2"
                      >
                        <RefreshCw
                          aria-hidden="true"
                          className={[
                            'h-3.5 w-3.5',
                            retrying ? 'animate-spin' : '',
                          ]
                            .filter(Boolean)
                            .join(' ')}
                        />
                        {retrying ? 'Retrying…' : 'Retry'}
                      </button>
                    ) : null}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
