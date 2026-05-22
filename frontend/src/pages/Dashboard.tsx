import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  CheckCircle2,
  FileWarning,
  Loader2,
  Send,
  Users,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { useSubmissions } from '@/hooks/useSubmissions';
import { useSuppliers } from '@/hooks/useSuppliers';
import { coisHooks } from '@/hooks/useArtifacts';
import { isWithinNextDays, isWithinPastDays } from '@/lib/dates';
import { extractErrorMessage } from '@/services/api';
import type { SubmissionListItem } from '@/services/api';
import EmptyState from '@/components/EmptyState';
import StatusPill from '@/components/StatusPill';

interface StatCardProps {
  label: string;
  value: string;
  icon: LucideIcon;
  tone?: 'default' | 'warn';
}

function StatCard({
  label,
  value,
  icon: Icon,
  tone = 'default',
}: StatCardProps): JSX.Element {
  const toneClass =
    tone === 'warn'
      ? 'border-amber-200 bg-amber-50 text-amber-900'
      : 'border-slate-200 bg-white text-slate-900';
  return (
    <div
      className={`rounded-lg border px-5 py-4 shadow-sm flex items-center gap-4 ${toneClass}`}
    >
      <div className="rounded-full bg-slate-900/5 p-2">
        <Icon className="h-5 w-5" aria-hidden="true" />
      </div>
      <div>
        <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
        <p className="text-2xl font-semibold">{value}</p>
      </div>
    </div>
  );
}

function isWithinPastDaysLocal(iso: string | null | undefined, days: number): boolean {
  return isWithinPastDays(iso, days);
}

export default function Dashboard(): JSX.Element {
  const { user } = useAuth();
  const suppliersQuery = useSuppliers({ pageSize: 100 });
  const submissionsQuery = useSubmissions({ pageSize: 100 });
  const recentQuery = useSubmissions({ pageSize: 10 });
  const coisQuery = coisHooks.useList({ limit: 200 });

  const stats = useMemo(() => {
    const suppliers = suppliersQuery.data ?? [];
    const all = submissionsQuery.data?.items ?? [];
    const thisWeek = all.filter((s) => isWithinPastDaysLocal(s.created_at, 7));
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

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">
          Welcome{user?.full_name ? `, ${user.full_name}` : ''}
        </h1>
        <p className="text-sm text-slate-500">
          Here is your submission activity at a glance.
        </p>
      </header>

      {error && (
        <div className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {extractErrorMessage(error, 'Failed to load dashboard data')}
        </div>
      )}

      <section
        aria-label="Key metrics"
        className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
      >
        <StatCard
          label="Active suppliers"
          value={loading ? '…' : stats.activeSuppliers}
          icon={Users}
        />
        <StatCard
          label="Submissions this week"
          value={loading ? '…' : stats.submissionsThisWeek}
          icon={Send}
        />
        <StatCard
          label="Success rate"
          value={loading ? '…' : stats.successRate}
          icon={CheckCircle2}
        />
        <StatCard
          label="Expiring COIs (≤30d)"
          value={loading ? '…' : stats.expiringCois}
          icon={FileWarning}
          tone={Number(stats.expiringCois) > 0 ? 'warn' : 'default'}
        />
      </section>

      <section className="rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3">
          <h2 className="text-sm font-semibold text-slate-900">
            Recent submissions
          </h2>
          <Link
            to="/submissions"
            className="text-xs font-medium text-slate-700 underline hover:no-underline"
          >
            View all
          </Link>
        </div>

        {recentQuery.isLoading ? (
          <div className="flex items-center justify-center py-12 text-slate-500">
            <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
            <span className="ml-2 text-sm">Loading…</span>
          </div>
        ) : recentQuery.error ? (
          <div className="px-5 py-8 text-sm text-red-700">
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
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-5 py-2 font-medium">Submission</th>
                  <th className="px-5 py-2 font-medium">Supplier</th>
                  <th className="px-5 py-2 font-medium">Portal</th>
                  <th className="px-5 py-2 font-medium">Status</th>
                  <th className="px-5 py-2 font-medium">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {recent.map((row) => (
                  <tr key={row.id} className="hover:bg-slate-50">
                    <td className="px-5 py-2 font-mono text-xs text-slate-700">
                      {row.id.slice(0, 8)}
                    </td>
                    <td className="px-5 py-2 font-mono text-xs text-slate-500">
                      {row.supplier_id.slice(0, 8)}
                    </td>
                    <td className="px-5 py-2 font-mono text-xs text-slate-500">
                      {row.portal_id.slice(0, 8)}
                    </td>
                    <td className="px-5 py-2">
                      <StatusPill status={row.status} />
                    </td>
                    <td className="px-5 py-2 text-slate-500">
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
