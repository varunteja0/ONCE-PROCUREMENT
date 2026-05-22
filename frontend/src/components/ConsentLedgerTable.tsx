import EmptyState from '@/components/EmptyState';
import type { ConsentRecord } from '@/services/api';

export interface ConsentLedgerRow extends ConsentRecord {
  supplier_name?: string | null;
}

export interface ConsentLedgerTableProps {
  items: readonly ConsentLedgerRow[];
  className?: string;
}

function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString();
}

function signatureSnippet(sig: string): string {
  if (!sig) return '—';
  if (sig.length <= 18) return sig;
  return `${sig.slice(0, 10)}…${sig.slice(-6)}`;
}

const SCOPE_LABEL: Record<ConsentRecord['scope'], string> = {
  read_only: 'Read only',
  submit_on_behalf: 'Submit on behalf',
  submit_and_sign: 'Submit & sign',
};

export default function ConsentLedgerTable({
  items,
  className,
}: ConsentLedgerTableProps): JSX.Element {
  if (items.length === 0) {
    return (
      <EmptyState
        title="No consent records"
        description="Signed consent grants from suppliers will appear here, forming an append-only audit ledger."
      />
    );
  }

  return (
    <div
      className={[
        'overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm',
        className ?? '',
      ]
        .filter(Boolean)
        .join(' ')}
    >
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <caption className="sr-only">Consent records ledger</caption>
        <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-600">
          <tr>
            <th scope="col" className="px-4 py-3">
              Supplier
            </th>
            <th scope="col" className="px-4 py-3">
              Scope
            </th>
            <th scope="col" className="px-4 py-3">
              Granted at
            </th>
            <th scope="col" className="px-4 py-3">
              Revoked at
            </th>
            <th scope="col" className="px-4 py-3">
              Signature
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {items.map((row) => {
            const isActive = row.revoked_at === null;
            return (
              <tr key={row.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-slate-900">
                  {row.supplier_name ?? (
                    <span className="font-mono text-xs text-slate-500">
                      {row.supplier_id}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700 ring-1 ring-inset ring-slate-200">
                    {SCOPE_LABEL[row.scope]}
                  </span>
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                  {formatDate(row.granted_at)}
                </td>
                <td className="whitespace-nowrap px-4 py-3">
                  {isActive ? (
                    <span
                      className="inline-flex items-center rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800 ring-1 ring-inset ring-emerald-200"
                      aria-label="Consent is active"
                    >
                      Active
                    </span>
                  ) : (
                    <span
                      className="text-slate-600"
                      aria-label={`Revoked at ${formatDate(row.revoked_at)}`}
                    >
                      {formatDate(row.revoked_at)}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <code
                    title={row.signature_b64}
                    className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700"
                  >
                    {signatureSnippet(row.signature_b64)}
                  </code>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
