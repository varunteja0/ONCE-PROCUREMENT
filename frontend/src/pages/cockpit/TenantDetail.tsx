import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { cockpitGetTenant } from '@/services/cockpitApi';
import { useCockpit } from '@/hooks/useCockpit';
import { Button } from '@/components/ui/Button';
import { toast } from '@/lib/toast';

export default function CockpitTenantDetail(): JSX.Element {
  const { tenantId = '' } = useParams<{ tenantId: string }>();
  const { switchActAs } = useCockpit();
  const { data, isLoading, error } = useQuery({
    queryKey: ['cockpit', 'tenant', tenantId],
    queryFn: () => cockpitGetTenant(tenantId),
    enabled: tenantId.length > 0,
  });

  async function handleActAs(): Promise<void> {
    if (!data) return;
    try {
      await switchActAs(data.id);
      toast.success(`Now acting as ${data.name}`);
    } catch (err) {
      toast.error(err, 'Failed to switch tenant');
    }
  }

  if (isLoading) return <p className="text-sm text-slate-500">Loading…</p>;
  if (error || !data) {
    return <p className="text-sm text-red-600">Tenant not found or inaccessible.</p>;
  }

  return (
    <div className="space-y-4" data-testid="cockpit-tenant-detail">
      <header>
        <Link
          to="/cockpit/tenants"
          className="text-xs text-amber-800 underline dark:text-amber-200"
        >
          ← All tenants
        </Link>
        <h1 className="mt-1 text-xl font-semibold text-amber-900 dark:text-amber-100">
          {data.name}
        </h1>
        <p className="text-sm text-slate-600 dark:text-slate-400">
          slug <code>{data.slug}</code> · plan <strong>{data.plan}</strong>
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Field label="Suppliers" value={data.supplier_count} />
        <Field label="Submissions" value={data.submission_count} />
        <Field
          label="Last activity"
          value={
            data.last_activity_at
              ? new Date(data.last_activity_at).toLocaleString()
              : '—'
          }
        />
      </div>

      <div>
        <Button onClick={() => void handleActAs()} disabled={!data.is_active}>
          Act as this tenant
        </Button>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
}: {
  label: string;
  value: string | number;
}): JSX.Element {
  return (
    <div className="rounded border border-amber-200 bg-white p-3 dark:border-amber-900 dark:bg-slate-900">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-base font-medium text-amber-900 dark:text-amber-100">
        {value}
      </p>
    </div>
  );
}
