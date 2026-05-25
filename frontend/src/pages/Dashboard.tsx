import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileWarning,
  Send,
  Users,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { useSubmissions } from '@/hooks/useSubmissions';
import { useSuppliers } from '@/hooks/useSuppliers';
import { usePortals } from '@/hooks/usePortals';
import { coisHooks } from '@/hooks/useArtifacts';
import { isWithinNextDays, isWithinPastDays } from '@/lib/dates';
import { downloadCsv, toCsv } from '@/lib/csv';
import { toast } from '@/lib/toast';
import { extractErrorMessage } from '@/services/api';
import type { SubmissionListItem } from '@/services/api';
import {
  Button,
  EmptyState,
  Skeleton,
  StatusBadge,
} from '@/components/ui';

interface StatCardProps {
  label: string;
  value: string;
  icon: LucideIcon;
  loading: boolean;
  tone?: 'default' | 'warn';
}

function StatCard({
  label,
  value,
  icon: Icon,
  loading,
  tone = 'default',
}: StatCardProps): JSX.Element {
  const toneClass =
    tone === 'warn'
      ? 'border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200'
      : 'border-slate-200 bg-white text-slate-900 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100';
  return (
    <div
      className={`rounded-lg border px-5 py-4 shadow-sm flex items-center gap-4 ${toneClass}`}
    >
      <div className="rounded-full bg-slate-900/5 p-2 dark:bg-slate-100/10">
        <Icon className="h-5 w-5" aria-hidden="true" />
      </div>
      <div className="min-w-0">
        <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
          {label}
        </p>
        {loading ? (
          <Skeleton className="mt-1 h-7 w-16" />
        ) : (
          <p className="text-2xl font-semibold">{value}</p>
        )}
      </div>
    </div>
  );
}

export default function Dashboard(): JSX.Element {
  const { user } = useAuth();
  const suppliersQuery = useSuppliers({ pageSize: 100 });
  // BACKEND-COUPLED: this page derives totals from in-memory lists. Once a
  // dedicated `/metrics/dashboard` endpoint exists, hydrate these counts from
  // its response instead of paging the full submission list.
  const submissionsQuery = useSubmissions({ pageSize: 100 });
  const recentQuery = useSubmissions({ pageSize: 10 });
  const coisQuery = coisHooks.useList({ limit: 200 });
  const portalsQuery = usePortals({ pageSize: 200 });

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

  const stats = useMemo(() => {
    const suppliers = suppliersQuery.data ?? [];
    const all = submissionsQuery.data?.items ?? [];
    const thisWeek = all.filter((s) => isWithinPastDays(s.created_at, 7));
    const completed = all.filter((s) => s.status === 'completed').length;
    const finished = all.filter(
      (s) =>
        s.status === 'completed' ||
        s.status === 'failed' ||
        s.status === 'blocked' ||
        s.status === 'platform_unsupported',
    ).length;
    const successRate =
      finished === 0 ? '—' : `${Math.round((completed / finished) * 100)}%`;

    const cois = coisQuery.data?.items ?? [];
    const expiringCount = cois.filter((c) =>
      isWithinNextDays(c.expires_at, 30),
    ).length;

    return {
      activeSuppliers: String(suppliers.length),
      submissionsThisWeek: String(thisWeek.length),
      successRate,
      expiringCois: String(expiringCount),
    };
  }, [submissionsQuery.data, suppliersQuery.data, coisQuery.data]);

  const recent: SubmissionListItem[] = recentQuery.data?.items ?? [];
  const loading =
    suppliersQuery.isLoading ||
    submissionsQuery.isLoading ||
    recentQuery.isLoading;
  const error = suppliersQuery.error ?? submissionsQuery.error ?? recentQuery.error;

  function exportRecent(): void {
    if (recent.length === 0) {
      toast.error('Nothing to export yet.');
      return;
    }
    const csv = toCsv(recent, [
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
      { header: 'Created', value: (r) => r.created_at },
      { header: 'Updated', value: (r) => r.updated_at },
    ]);
    downloadCsv(`recent-submissions-${new Date().toISOString().slice(0, 10)}.csv`, csv);
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
          Welcome{user?.full_name ? `, ${user.full_name}` : ''}
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Here is your submission activity at a glance.
        </p>
      </header>

      {error && (
        <div className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/30 dark:text-red-200">
          {extractErrorMessage(error, 'Failed to load dashboard data')}
        </div>
      )}

      <section
        aria-label="Key metrics"
        className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
      >
        <StatCard
          label="Active suppliers"
          value={stats.activeSuppliers}
          icon={Users}
          loading={loading}
        />
        <StatCard
          label="Submissions this week"
          value={stats.submissionsThisWeek}
          icon={Send}
          loading={loading}
        />
        <StatCard
          label="Success rate"
          value={stats.successRate}
          icon={CheckCircle2}
          loading={loading}
        />
        <StatCard
          label="Expiring COIs (≤30d)"
          value={stats.expiringCois}
          icon={FileWarning}
          loading={loading}
          tone={Number(stats.expiringCois) > 0 ? 'warn' : 'default'}
        />
      </section>

      <section className="rounded-lg border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3 dark:border-slate-800">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            Recent submissions
          </h2>
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={exportRecent}
              disabled={recent.length === 0}
              leadingIcon={<Download className="h-3.5 w-3.5" />}
            >
              Export recent
            </Button>
            <Link
              to="/submissions"
              className="text-xs font-medium text-slate-700 underline hover:no-underline dark:text-slate-200"
            >
              View all
            </Link>
          </div>
        </div>

        {recentQuery.isLoading ? (
          <div className="space-y-2 p-5" aria-busy="true">
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-6 w-full" />
          </div>
        ) : recentQuery.error ? (
          <div className="px-5 py-8 text-sm text-red-700 dark:text-red-300">
            {extractErrorMessage(recentQuery.error, 'Failed to load submissions')}
          </div>
        ) : recent.length === 0 ? (
          <div className="px-5 py-8">
            <EmptyState
              title="No submissions yet"
              description="Submissions will appear here once you start sending them."
              icon={AlertTriangle}
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
                  <th className="px-5 py-2 font-medium">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {recent.map((row) => (
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
                    <td className="px-5 py-2 text-slate-500 dark:text-slate-400">
                      {new Date(row.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
