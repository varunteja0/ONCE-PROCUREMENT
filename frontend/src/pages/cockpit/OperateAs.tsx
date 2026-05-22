import { useCockpit, useCockpitTenants } from '@/hooks/useCockpit';
import { Button } from '@/components/ui/Button';
import { toast } from '@/lib/toast';

export default function CockpitOperateAs(): JSX.Element {
  const { actingAsTenantId, switchActAs } = useCockpit();
  const { data, isLoading } = useCockpitTenants();

  async function pick(tenantId: string, name: string): Promise<void> {
    try {
      await switchActAs(tenantId);
      toast.success(`Now acting as ${name}`);
    } catch (err) {
      toast.error(err, 'Failed to switch tenant');
    }
  }

  return (
    <div className="space-y-4" data-testid="cockpit-operate-as">
      <header>
        <h1 className="text-xl font-semibold text-amber-900 dark:text-amber-100">
          Operate as tenant
        </h1>
        <p className="text-sm text-slate-600 dark:text-slate-400">
          Pick a tenant to scope subsequent API calls. All actions performed
          while acting as a tenant are recorded in the cockpit audit log.
        </p>
      </header>

      {actingAsTenantId ? (
        <div className="rounded border border-amber-300 bg-amber-100 p-3 text-sm dark:border-amber-700 dark:bg-amber-900/40">
          Currently acting as <code>{actingAsTenantId}</code>.{' '}
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              void switchActAs(null);
            }}
          >
            Exit
          </Button>
        </div>
      ) : null}

      {isLoading ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : (
        <ul className="divide-y divide-amber-100 overflow-hidden rounded border border-amber-200 bg-white dark:divide-amber-900 dark:border-amber-900 dark:bg-slate-900">
          {data?.items.map((t) => (
            <li key={t.id} className="flex items-center justify-between px-3 py-2 text-sm">
              <div>
                <p className="font-medium text-amber-900 dark:text-amber-100">{t.name}</p>
                <p className="text-xs text-slate-500">{t.slug} · {t.plan}</p>
              </div>
              <Button
                size="sm"
                disabled={!t.is_active || t.id === actingAsTenantId}
                onClick={() => void pick(t.id, t.name)}
              >
                {t.id === actingAsTenantId ? 'Active' : 'Act as'}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
