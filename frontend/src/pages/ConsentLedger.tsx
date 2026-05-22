import { Loader2 } from 'lucide-react';
import ConsentLedgerTable from '@/components/ConsentLedgerTable';
import { useConsents } from '@/hooks/useConsents';
import { extractErrorMessage } from '@/services/api';

export default function ConsentLedger(): JSX.Element {
  const query = useConsents({ limit: 200 });
  const items = query.data?.items ?? [];

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
          Consent ledger
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Every signed authorization that lets Once act on behalf of a supplier.
        </p>
      </header>

      {query.isLoading ? (
        <div className="flex items-center justify-center rounded-lg border border-slate-200 bg-white py-12 text-slate-500 shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
          <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
          <span className="ml-2 text-sm">Loading consents…</span>
        </div>
      ) : query.error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-5 py-8 text-sm text-red-800 dark:border-red-800 dark:bg-red-950/30 dark:text-red-200">
          {extractErrorMessage(query.error, 'Failed to load consents')}
        </div>
      ) : (
        <ConsentLedgerTable items={items} />
      )}
    </div>
  );
}
