import { useState } from 'react';
import { useCockpitAudit } from '@/hooks/useCockpit';
import { Input } from '@/components/ui/Input';

export default function CockpitAuditLog(): JSX.Element {
  const [tenantFilter, setTenantFilter] = useState('');
  const [operatorFilter, setOperatorFilter] = useState('');
  const { data, isLoading } = useCockpitAudit({
    limit: 100,
    tenant_id: tenantFilter || undefined,
    operator_id: operatorFilter || undefined,
  });

  return (
    <div className="space-y-4" data-testid="cockpit-audit-log">
      <header>
        <h1 className="text-xl font-semibold text-amber-900 dark:text-amber-100">
          Cockpit audit log
        </h1>
        <p className="text-sm text-slate-600 dark:text-slate-400">
          Append-only. Sensitive payload keys are redacted server-side.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Input
          label="Filter by tenant id"
          value={tenantFilter}
          onChange={(e) => setTenantFilter(e.target.value)}
        />
        <Input
          label="Filter by operator id"
          value={operatorFilter}
          onChange={(e) => setOperatorFilter(e.target.value)}
        />
      </div>

      {isLoading ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : (
        <div className="overflow-x-auto rounded border border-amber-200 bg-white dark:border-amber-900 dark:bg-slate-900">
          <table className="w-full text-xs">
            <thead className="bg-amber-100 text-left uppercase text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
              <tr>
                <th className="px-2 py-2">When</th>
                <th className="px-2 py-2">Operator</th>
                <th className="px-2 py-2">Tenant</th>
                <th className="px-2 py-2">Action</th>
                <th className="px-2 py-2">Method</th>
                <th className="px-2 py-2">Path</th>
                <th className="px-2 py-2">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-amber-100 dark:divide-amber-900">
              {data?.items.map((e) => (
                <tr key={e.id}>
                  <td className="px-2 py-1 whitespace-nowrap">
                    {new Date(e.occurred_at).toLocaleString()}
                  </td>
                  <td className="px-2 py-1 font-mono">{e.operator_id ?? '—'}</td>
                  <td className="px-2 py-1 font-mono">{e.tenant_id_acted_as ?? '—'}</td>
                  <td className="px-2 py-1">{e.action}</td>
                  <td className="px-2 py-1">{e.method ?? '—'}</td>
                  <td className="px-2 py-1 font-mono">{e.path ?? '—'}</td>
                  <td className="px-2 py-1 tabular-nums">{e.status_code ?? '—'}</td>
                </tr>
              ))}
              {data?.items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-2 py-6 text-center text-slate-500">
                    No audit events match these filters.
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
