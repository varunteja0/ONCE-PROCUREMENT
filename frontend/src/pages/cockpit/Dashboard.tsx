import { Link } from 'react-router-dom';
import { useCockpit, useCockpitTenants, useCockpitAudit } from '@/hooks/useCockpit';

export default function CockpitDashboard(): JSX.Element {
  const { operator } = useCockpit();
  const tenants = useCockpitTenants();
  const audit = useCockpitAudit({ limit: 5 });

  const totalTenants = tenants.data?.total ?? 0;
  const activeTenants =
    tenants.data?.items.filter((t) => t.is_active).length ?? 0;
  const totalSubmissions =
    tenants.data?.items.reduce((sum, t) => sum + (t.submission_count ?? 0), 0) ??
    0;

  return (
    <div className="space-y-6" data-testid="cockpit-dashboard">
      <header>
        <h1 className="text-xl font-semibold text-amber-900 dark:text-amber-100">
          Welcome{operator ? `, ${operator.email.split('@')[0]}` : ''}
        </h1>
        <p className="text-sm text-slate-600 dark:text-slate-400">
          Role: <strong>{operator?.role ?? 'unknown'}</strong>
          {operator?.all_tenants ? ' · access to all tenants' : null}
        </p>
      </header>

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Stat label="Tenants" value={totalTenants} loading={tenants.isLoading} />
        <Stat label="Active tenants" value={activeTenants} loading={tenants.isLoading} />
        <Stat label="Total submissions" value={totalSubmissions} loading={tenants.isLoading} />
      </section>

      <section>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
            Recent audit events
          </h2>
          <Link
            to="/cockpit/audit"
            className="text-xs font-medium text-amber-800 underline dark:text-amber-200"
          >
            View all
          </Link>
        </div>
        <div className="overflow-hidden rounded border border-amber-200 bg-white dark:border-amber-900 dark:bg-slate-900">
          {audit.isLoading ? (
            <div className="p-4 text-sm text-slate-500">Loading…</div>
          ) : audit.data && audit.data.items.length > 0 ? (
            <ul className="divide-y divide-amber-100 dark:divide-amber-900">
              {audit.data.items.map((entry) => (
                <li key={entry.id} className="px-4 py-2 text-sm">
                  <code className="mr-2 text-xs text-amber-700 dark:text-amber-300">
                    {entry.action}
                  </code>
                  <span className="text-slate-700 dark:text-slate-300">
                    {entry.path ?? entry.resource_type}
                  </span>
                  <span className="ml-2 text-xs text-slate-400">
                    {new Date(entry.occurred_at).toLocaleString()}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="p-4 text-sm text-slate-500">No audit events yet.</div>
          )}
        </div>
      </section>
    </div>
  );
}

function Stat({
  label,
  value,
  loading,
}: {
  label: string;
  value: number;
  loading: boolean;
}): JSX.Element {
  return (
    <div className="rounded border border-amber-200 bg-white p-4 dark:border-amber-900 dark:bg-slate-900">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-amber-900 dark:text-amber-100">
        {loading ? '…' : value}
      </p>
    </div>
  );
}
