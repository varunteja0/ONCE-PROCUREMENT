import { useCockpit } from '@/hooks/useCockpit';

export default function CockpitAccount(): JSX.Element {
  const { operator } = useCockpit();
  if (!operator) return <p className="text-sm text-slate-500">Loading…</p>;

  return (
    <div className="space-y-4" data-testid="cockpit-account">
      <h1 className="text-xl font-semibold text-amber-900 dark:text-amber-100">
        Account
      </h1>
      <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Row label="Email" value={operator.email} />
        <Row label="Role" value={operator.role} />
        <Row label="Status" value={operator.status} />
        <Row label="MFA required" value={operator.mfa_required ? 'yes' : 'no'} />
        <Row
          label="Last login"
          value={
            operator.last_login_at
              ? new Date(operator.last_login_at).toLocaleString()
              : '—'
          }
        />
        <Row label="All tenants" value={operator.all_tenants ? 'yes' : 'no'} />
      </dl>
      {!operator.all_tenants ? (
        <section>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
            Accessible tenants
          </h2>
          <ul className="mt-1 list-disc pl-5 text-sm text-slate-700 dark:text-slate-300">
            {operator.accessible_tenant_ids.map((id) => (
              <li key={id}>
                <code>{id}</code>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded border border-amber-200 bg-white p-3 dark:border-amber-900 dark:bg-slate-900">
      <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-1 text-sm font-medium text-amber-900 dark:text-amber-100">
        {value}
      </dd>
    </div>
  );
}
