import { Link } from 'react-router-dom';
import { useCockpit, useCockpitTenants } from '@/hooks/useCockpit';
import { Button } from '@/components/ui/Button';
import { toast } from '@/lib/toast';

export default function CockpitTenantList(): JSX.Element {
  const { switchActAs } = useCockpit();
  const { data, isLoading, error, refetch } = useCockpitTenants();

  async function handleActAs(tenantId: string, name: string): Promise<void> {
    try {
      await switchActAs(tenantId);
      toast.success(`Now acting as ${name}`);
    } catch (err) {
      toast.error(err, 'Failed to switch tenant');
    }
  }

  return (
    <div className="space-y-4" data-testid="cockpit-tenants">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-amber-900 dark:text-amber-100">
          Tenants
        </h1>
        <Button size="sm" variant="ghost" onClick={() => void refetch()}>
          Refresh
        </Button>
      </header>

      {isLoading ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : error ? (
        <p className="text-sm text-red-600">Failed to load tenants.</p>
      ) : (
        <div className="overflow-hidden rounded border border-amber-200 bg-white dark:border-amber-900 dark:bg-slate-900">
          <table className="w-full text-sm">
            <thead className="bg-amber-100 text-left text-xs uppercase tracking-wide text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
              <tr>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Slug</th>
                <th className="px-3 py-2">Plan</th>
                <th className="px-3 py-2">Suppliers</th>
                <th className="px-3 py-2">Submissions</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-amber-100 dark:divide-amber-900">
              {data?.items.map((t) => (
                <tr key={t.id}>
                  <td className="px-3 py-2 font-medium">
                    <Link
                      to={`/cockpit/tenants/${t.id}`}
                      className="text-amber-800 underline dark:text-amber-200"
                    >
                      {t.name}
                    </Link>
                  </td>
                  <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{t.slug}</td>
                  <td className="px-3 py-2">{t.plan}</td>
                  <td className="px-3 py-2 tabular-nums">{t.supplier_count}</td>
                  <td className="px-3 py-2 tabular-nums">{t.submission_count}</td>
                  <td className="px-3 py-2">
                    <span
                      className={
                        t.is_active
                          ? 'rounded bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700'
                          : 'rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600'
                      }
                    >
                      {t.is_active ? 'active' : 'inactive'}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={!t.is_active}
                      onClick={() => void handleActAs(t.id, t.name)}
                    >
                      Act as
                    </Button>
                  </td>
                </tr>
              ))}
              {data?.items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-3 py-6 text-center text-sm text-slate-500">
                    No tenants visible to this operator.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
