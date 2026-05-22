import { useState } from 'react';
import { Link } from 'react-router-dom';
import { FileCheck2, Loader2, X } from 'lucide-react';
import { useReceipts } from '@/hooks/useReceipts';
import { extractErrorMessage } from '@/services/api';
import type { Receipt } from '@/services/api';
import EmptyState from '@/components/EmptyState';
import ReceiptVerifierWidget from '@/components/ReceiptVerifierWidget';

export default function Receipts(): JSX.Element {
  const query = useReceipts({ pageSize: 100 });
  const [active, setActive] = useState<Receipt | null>(null);

  const receipts = query.data ?? [];

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Receipts</h1>
        <p className="text-sm text-slate-500">
          Ed25519-signed proof of every successful submission. Click a receipt
          to verify.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-lg border border-slate-200 bg-white shadow-sm">
          {query.isLoading ? (
            <div className="flex items-center justify-center py-12 text-slate-500">
              <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
              <span className="ml-2 text-sm">Loading receipts…</span>
            </div>
          ) : query.error ? (
            <div className="px-5 py-8 text-sm text-red-700">
              {extractErrorMessage(query.error, 'Failed to load receipts')}
            </div>
          ) : receipts.length === 0 ? (
            <div className="px-5 py-12">
              <EmptyState
                title="No receipts yet"
                description="Receipts will appear here once a submission completes successfully."
                icon={FileCheck2}
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-5 py-2 font-medium">Receipt</th>
                    <th className="px-5 py-2 font-medium">Portal</th>
                    <th className="px-5 py-2 font-medium">Submitted</th>
                    <th className="px-5 py-2 font-medium">Key</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {receipts.map((r) => {
                    const isActive = active?.id === r.id;
                    return (
                      <tr
                        key={r.id}
                        className={
                          isActive ? 'bg-slate-100' : 'hover:bg-slate-50'
                        }
                      >
                        <td className="px-5 py-2">
                          <Link
                            to={`/receipts/${r.id}`}
                            className="font-mono text-xs text-slate-700 underline hover:no-underline"
                          >
                            {r.id.slice(0, 8)}
                          </Link>
                          <button
                            type="button"
                            onClick={() => setActive(r)}
                            className="ml-2 text-xs text-slate-500 hover:underline"
                          >
                            Quick verify
                          </button>
                        </td>
                        <td className="px-5 py-2 text-slate-700">
                          {r.portal_platform}
                        </td>
                        <td className="px-5 py-2 text-slate-500">
                          {new Date(r.submitted_at).toLocaleString()}
                        </td>
                        <td className="px-5 py-2 font-mono text-xs text-slate-500">
                          {r.signing_key_id}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <aside className="rounded-lg border border-slate-200 bg-white shadow-sm">
          <div className="flex items-center justify-between border-b border-slate-200 px-4 py-2">
            <h2 className="text-sm font-semibold text-slate-900">
              Verification
            </h2>
            {active && (
              <button
                type="button"
                onClick={() => setActive(null)}
                className="rounded p-1 text-slate-500 hover:bg-slate-100"
                aria-label="Close verifier"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            )}
          </div>
          <div className="p-4">
            {active ? (
              <ReceiptVerifierWidget receiptId={active.id} />
            ) : (
              <p className="text-sm text-slate-500">
                Select a receipt to view its cryptographic verification.
              </p>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
