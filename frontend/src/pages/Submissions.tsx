import { useMemo, useState, type ChangeEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ChevronLeft, ChevronRight, Inbox, Loader2, RefreshCw } from 'lucide-react';
import {
  useSubmissions,
  useRetrySubmission,
} from '@/hooks/useSubmissions';
import { extractErrorMessage } from '@/services/api';
import type { SubmissionListItem, SubmissionStatus } from '@/services/api';
import EmptyState from '@/components/EmptyState';
import StatusPill from '@/components/StatusPill';
import { Button } from '@/components/ui/Button';
import { toast } from '@/lib/toast';

const STATUS_OPTIONS: ReadonlyArray<{ value: '' | SubmissionStatus; label: string }> = [
  { value: '', label: 'All statuses' },
  { value: 'queued', label: 'Queued' },
  { value: 'running', label: 'Running' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
  { value: 'retrying', label: 'Retrying' },
  { value: 'blocked', label: 'Blocked' },
  { value: 'platform_unsupported', label: 'Platform unsupported' },
];

const PAGE_SIZE = 25;

function isRetriable(status: SubmissionStatus): boolean {
  return status === 'failed' || status === 'blocked';
}

const ALLOWED_STATUSES: ReadonlyArray<SubmissionStatus> = [
  'queued',
  'running',
  'completed',
  'failed',
  'retrying',
  'blocked',
  'platform_unsupported',
];

function parseStatus(raw: string | null): '' | SubmissionStatus {
  if (!raw) return '';
  return (ALLOWED_STATUSES as ReadonlyArray<string>).includes(raw)
    ? (raw as SubmissionStatus)
    : '';
}

export default function Submissions(): JSX.Element {
  const [params, setParams] = useSearchParams();
  const status = parseStatus(params.get('status'));
  const page = Math.max(1, Number(params.get('page') ?? '1'));

  const query = useSubmissions(
    useMemo(
      () => ({
        ...(status === '' ? {} : { status }),
        page,
        pageSize: PAGE_SIZE,
      }),
      [status, page],
    ),
  );
  const retry = useRetrySubmission();

  const items: SubmissionListItem[] = query.data?.items ?? [];
  const hasNext = items.length === PAGE_SIZE;

  const [retryingId, setRetryingId] = useState<string | null>(null);

  function onStatusChange(e: ChangeEvent<HTMLSelectElement>): void {
    const next = e.target.value;
    setParams((prev) => {
      const out = new URLSearchParams(prev);
      if (next === '') out.delete('status');
      else out.set('status', next);
      out.set('page', '1');
      return out;
    });
  }

  function setPage(updater: (current: number) => number): void {
    setParams((prev) => {
      const out = new URLSearchParams(prev);
      out.set('page', String(updater(page)));
      return out;
    });
  }

  async function onRetry(id: string): Promise<void> {
    setRetryingId(id);
    try {
      await retry.mutateAsync(id);
      toast.success('Submission requeued.');
    } catch (err) {
      toast.error(err, 'Retry failed');
    } finally {
      setRetryingId(null);
    }
  }

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
            Submissions
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Every submission attempt across every carrier portal.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link to="/submissions/new">
            <Button variant="primary" size="sm">
              New submission
            </Button>
          </Link>
          <label htmlFor="status_filter" className="sr-only">
            Filter by status
          </label>
          <select
            id="status_filter"
            value={status}
            onChange={onStatusChange}
            className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </header>

      <div className="rounded-lg border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
        {query.isLoading ? (
          <div className="flex items-center justify-center py-12 text-slate-500 dark:text-slate-400">
            <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
            <span className="ml-2 text-sm">Loading submissions…</span>
          </div>
        ) : query.error ? (
          <div className="px-5 py-8 text-sm text-red-700 dark:text-red-400">
            {extractErrorMessage(query.error, 'Failed to load submissions')}
          </div>
        ) : items.length === 0 ? (
          <div className="px-5 py-12">
            <EmptyState
              title="No submissions found"
              description={
                status === ''
                  ? 'You have not submitted anything yet.'
                  : 'No submissions match the selected filter.'
              }
              icon={Inbox}
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500 dark:bg-slate-800/60 dark:text-slate-400">
                <tr>
                  <th className="px-5 py-2 font-medium">Submission</th>
                  <th className="px-5 py-2 font-medium">Supplier</th>
                  <th className="px-5 py-2 font-medium">Portal</th>
                  <th className="px-5 py-2 font-medium">Status</th>
                  <th className="px-5 py-2 font-medium">Attempts</th>
                  <th className="px-5 py-2 font-medium">Updated</th>
                  <th className="px-5 py-2 font-medium" aria-label="Actions" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {items.map((row) => (
                  <tr
                    key={row.id}
                    className="hover:bg-slate-50 dark:hover:bg-slate-800/50"
                  >
                    <td className="px-5 py-2">
                      <Link
                        to={`/submissions/${row.id}`}
                        className="font-mono text-xs text-slate-700 underline hover:no-underline dark:text-slate-200"
                      >
                        {row.id.slice(0, 8)}
                      </Link>
                    </td>
                    <td className="px-5 py-2 font-mono text-xs text-slate-500 dark:text-slate-400">
                      {row.supplier_id.slice(0, 8)}
                    </td>
                    <td className="px-5 py-2 font-mono text-xs text-slate-500 dark:text-slate-400">
                      {row.portal_id.slice(0, 8)}
                    </td>
                    <td className="px-5 py-2">
                      <StatusPill status={row.status} />
                    </td>
                    <td className="px-5 py-2 text-slate-700 dark:text-slate-200">
                      {row.attempt_count}
                    </td>
                    <td className="px-5 py-2 text-slate-500 dark:text-slate-400">
                      {new Date(row.updated_at).toLocaleString()}
                    </td>
                    <td className="px-5 py-2 text-right">
                      {isRetriable(row.status) && (
                        <button
                          type="button"
                          onClick={() => void onRetry(row.id)}
                          disabled={retryingId === row.id}
                          className="inline-flex items-center gap-1 rounded border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-100 disabled:opacity-60 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
                        >
                          <RefreshCw
                            className={`h-3.5 w-3.5 ${
                              retryingId === row.id ? 'animate-spin' : ''
                            }`}
                            aria-hidden="true"
                          />
                          Retry
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex items-center justify-between border-t border-slate-200 px-5 py-2 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
          <span>
            Page {page}
            {items.length > 0 ? ` · ${items.length} rows` : ''}
          </span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1 || query.isLoading}
              className="rounded border border-slate-300 px-2 py-1 hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:hover:bg-slate-800"
              aria-label="Previous page"
            >
              <ChevronLeft className="h-4 w-4" aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={() => setPage((p) => p + 1)}
              disabled={!hasNext || query.isLoading}
              className="rounded border border-slate-300 px-2 py-1 hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:hover:bg-slate-800"
              aria-label="Next page"
            >
              <ChevronRight className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
