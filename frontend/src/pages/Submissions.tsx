import { useMemo, useState, type ChangeEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Download, Inbox, RefreshCw } from 'lucide-react';
import {
  useSubmissions,
  useRetrySubmission,
} from '@/hooks/useSubmissions';
import { useSuppliers } from '@/hooks/useSuppliers';
import { usePortals } from '@/hooks/usePortals';
import { extractErrorMessage } from '@/services/api';
import type { SubmissionListItem, SubmissionStatus } from '@/services/api';
import {
  Button,
  EmptyState,
  PaginationControls,
  Skeleton,
  StatusBadge,
} from '@/components/ui';
import { downloadCsv, toCsv } from '@/lib/csv';
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

function withinDateRange(iso: string, from: string, to: string): boolean {
  if (!from && !to) return true;
  const ts = Date.parse(iso);
  if (Number.isNaN(ts)) return false;
  if (from) {
    const f = Date.parse(from);
    if (!Number.isNaN(f) && ts < f) return false;
  }
  if (to) {
    const t = Date.parse(`${to}T23:59:59.999Z`);
    if (!Number.isNaN(t) && ts > t) return false;
  }
  return true;
}

export default function Submissions(): JSX.Element {
  const [params, setParams] = useSearchParams();
  const status = parseStatus(params.get('status'));
  const supplierId = params.get('supplier') ?? '';
  const portalId = params.get('portal') ?? '';
  const dateFrom = params.get('from') ?? '';
  const dateTo = params.get('to') ?? '';
  const page = Math.max(1, Number(params.get('page') ?? '1'));

  const query = useSubmissions(
    useMemo(
      () => ({
        ...(status === '' ? {} : { status }),
        ...(supplierId ? { supplierId } : {}),
        ...(portalId ? { portalId } : {}),
        page,
        pageSize: PAGE_SIZE,
      }),
      [status, supplierId, portalId, page],
    ),
  );
  const suppliersQuery = useSuppliers({ pageSize: 200 });
  const portalsQuery = usePortals({ pageSize: 200 });
  const retry = useRetrySubmission();

  const supplierNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const s of suppliersQuery.data ?? []) {
      map.set(s.id, s.legal_name);
    }
    return map;
  }, [suppliersQuery.data]);

  const portalNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const p of portalsQuery.data?.items ?? []) {
      map.set(p.id, p.display_name);
    }
    return map;
  }, [portalsQuery.data]);

  // Date filters are applied client-side: backend list endpoint has no `from`/`to`.
  const items = useMemo(() => {
    const rawItems: SubmissionListItem[] = query.data?.items ?? [];
    return rawItems.filter((r) => withinDateRange(r.created_at, dateFrom, dateTo));
  }, [query.data, dateFrom, dateTo]);

  const [retryingId, setRetryingId] = useState<string | null>(null);

  function patchParams(mutator: (p: URLSearchParams) => void): void {
    setParams((prev) => {
      const out = new URLSearchParams(prev);
      mutator(out);
      out.set('page', '1');
      return out;
    });
  }

  function onStatusChange(e: ChangeEvent<HTMLSelectElement>): void {
    const next = e.target.value;
    patchParams((p) => {
      if (next === '') p.delete('status');
      else p.set('status', next);
    });
  }

  function onSupplierChange(e: ChangeEvent<HTMLSelectElement>): void {
    const next = e.target.value;
    patchParams((p) => {
      if (next === '') p.delete('supplier');
      else p.set('supplier', next);
    });
  }

  function onPortalChange(e: ChangeEvent<HTMLSelectElement>): void {
    const next = e.target.value;
    patchParams((p) => {
      if (next === '') p.delete('portal');
      else p.set('portal', next);
    });
  }

  function onFromChange(e: ChangeEvent<HTMLInputElement>): void {
    const next = e.target.value;
    patchParams((p) => {
      if (!next) p.delete('from');
      else p.set('from', next);
    });
  }

  function onToChange(e: ChangeEvent<HTMLInputElement>): void {
    const next = e.target.value;
    patchParams((p) => {
      if (!next) p.delete('to');
      else p.set('to', next);
    });
  }

  function setPage(next: number): void {
    setParams((prev) => {
      const out = new URLSearchParams(prev);
      out.set('page', String(next));
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

  function exportCsv(): void {
    if (items.length === 0) {
      toast.error('Nothing to export.');
      return;
    }
    const csv = toCsv(items, [
      { header: 'Submission ID', value: (r) => r.id },
      {
        header: 'Supplier',
        value: (r) => supplierNameById.get(r.supplier_id) ?? r.supplier_id,
      },
      {
        header: 'Portal',
        value: (r) => portalNameById.get(r.portal_id) ?? r.portal_id,
      },
      { header: 'Status', value: (r) => r.status },
      { header: 'Attempts', value: (r) => r.attempt_count },
      { header: 'Last error', value: (r) => r.last_error ?? '' },
      { header: 'Created', value: (r) => r.created_at },
      { header: 'Updated', value: (r) => r.updated_at },
      { header: 'Completed', value: (r) => r.completed_at ?? '' },
    ]);
    downloadCsv(`submissions-${new Date().toISOString().slice(0, 10)}.csv`, csv);
  }

  // BACKEND-COUPLED: `/submissions` returns a bare array (no `total`), so
  // PaginationControls is given `total={null}` and shows "Page N".
  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
            Submissions
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Every submission attempt across every carrier portal.
          </p>
        </div>

        <div className="flex flex-wrap items-end gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={exportCsv}
            disabled={items.length === 0}
            leadingIcon={<Download className="h-3.5 w-3.5" />}
          >
            Export CSV
          </Button>
          <Link to="/submissions/new">
            <Button variant="primary" size="sm">
              New submission
            </Button>
          </Link>
        </div>
      </header>

      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
        <div>
          <label
            htmlFor="status_filter"
            className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-300"
          >
            Status
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
        <div>
          <label
            htmlFor="supplier_filter"
            className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-300"
          >
            Supplier
          </label>
          <select
            id="supplier_filter"
            value={supplierId}
            onChange={onSupplierChange}
            className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            <option value="">All suppliers</option>
            {(suppliersQuery.data ?? []).map((s) => (
              <option key={s.id} value={s.id}>
                {s.legal_name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label
            htmlFor="portal_filter"
            className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-300"
          >
            Portal
          </label>
          <select
            id="portal_filter"
            value={portalId}
            onChange={onPortalChange}
            className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            <option value="">All portals</option>
            {(portalsQuery.data?.items ?? []).map((p) => (
              <option key={p.id} value={p.id}>
                {p.display_name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label
            htmlFor="from_filter"
            className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-300"
          >
            From
          </label>
          <input
            id="from_filter"
            type="date"
            value={dateFrom}
            onChange={onFromChange}
            className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          />
        </div>
        <div>
          <label
            htmlFor="to_filter"
            className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-300"
          >
            To
          </label>
          <input
            id="to_filter"
            type="date"
            value={dateTo}
            onChange={onToChange}
            className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          />
        </div>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
        {query.isLoading ? (
          <div className="space-y-2 p-5" aria-busy="true">
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-6 w-full" />
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
                status === '' && !supplierId && !portalId && !dateFrom && !dateTo
                  ? 'You have not submitted anything yet.'
                  : 'No submissions match the selected filters.'
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
                    <td className="px-5 py-2 text-slate-700 dark:text-slate-200">
                      {supplierNameById.get(row.supplier_id) ?? (
                        <span className="font-mono text-xs text-slate-500 dark:text-slate-400">
                          {row.supplier_id.slice(0, 8)}
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-2 text-slate-700 dark:text-slate-200">
                      {portalNameById.get(row.portal_id) ?? (
                        <span className="font-mono text-xs text-slate-500 dark:text-slate-400">
                          {row.portal_id.slice(0, 8)}
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-2">
                      <StatusBadge status={row.status} />
                    </td>
                    <td className="px-5 py-2 text-slate-700 dark:text-slate-200">
                      {row.attempt_count}
                    </td>
                    <td className="px-5 py-2 text-slate-500 dark:text-slate-400">
                      {new Date(row.updated_at).toLocaleString()}
                    </td>
                    <td className="px-5 py-2 text-right">
                      {isRetriable(row.status) && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => void onRetry(row.id)}
                          loading={retryingId === row.id}
                          leadingIcon={<RefreshCw className="h-3.5 w-3.5" />}
                        >
                          Retry
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <PaginationControls
          page={page}
          pageSize={PAGE_SIZE}
          total={null}
          onPageChange={setPage}
          isLoading={query.isLoading}
        />
      </div>
    </div>
  );
}
