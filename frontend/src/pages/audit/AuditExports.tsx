// --- L3.10 audit ---
import { ExportDialog } from '@/components/audit/ExportDialog';
import { useAuditExports } from '@/hooks/useAudit';
import { auditApi } from '@/services/auditApi';
import { useState } from 'react';
import { Link } from 'react-router-dom';

const STATUS_TONE: Record<string, string> = {
  pending: 'bg-gray-100 text-gray-700',
  generating: 'bg-blue-100 text-blue-700',
  ready: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
};

export default function AuditExports() {
  const [open, setOpen] = useState(false);
  const { data, isLoading, isError, error } = useAuditExports();

  return (
    <div className="space-y-4 p-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Audit exports</h1>
        <div className="flex gap-2">
          <Link
            to="/audit"
            className="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-50"
          >
            ← Audit log
          </Link>
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white"
          >
            Generate export
          </button>
        </div>
      </div>

      {isLoading && <div className="text-sm text-gray-500">Loading…</div>}
      {isError && (
        <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
          {(error as Error).message}
        </div>
      )}

      {data && (
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b text-left text-xs uppercase tracking-wide text-gray-500">
              <th className="py-2 pr-2">Scope</th>
              <th className="py-2 pr-2">Status</th>
              <th className="py-2 pr-2">Rows</th>
              <th className="py-2 pr-2">Requested</th>
              <th className="py-2 pr-2">Expires</th>
              <th className="py-2 pr-2">Download</th>
            </tr>
          </thead>
          <tbody>
            {data.map((ex) => (
              <tr key={ex.id} className="border-b">
                <td className="py-2 pr-2">
                  <div className="font-medium">{ex.scope_type}</div>
                  {ex.scope_params && (
                    <div className="font-mono text-xs text-gray-500">
                      {JSON.stringify(ex.scope_params)}
                    </div>
                  )}
                </td>
                <td className="py-2 pr-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs ${STATUS_TONE[ex.status] ?? ''}`}
                  >
                    {ex.status}
                  </span>
                  {ex.error && (
                    <div className="text-xs text-red-600">{ex.error}</div>
                  )}
                </td>
                <td className="py-2 pr-2">{ex.row_count ?? '—'}</td>
                <td className="py-2 pr-2 text-xs text-gray-600">
                  {new Date(ex.requested_at).toLocaleString()}
                </td>
                <td className="py-2 pr-2 text-xs text-gray-600">
                  {ex.expires_at
                    ? new Date(ex.expires_at).toLocaleString()
                    : '—'}
                </td>
                <td className="py-2 pr-2">
                  {ex.status === 'ready' ? (
                    <div className="flex flex-col gap-1">
                      <a
                        className="text-blue-700 underline"
                        href={auditApi.downloadExportUrl(ex.id)}
                      >
                        PDF
                      </a>
                      <a
                        className="text-blue-700 underline"
                        href={auditApi.downloadEnvelopeUrl(ex.id)}
                      >
                        Envelope JSON
                      </a>
                    </div>
                  ) : (
                    '—'
                  )}
                </td>
              </tr>
            ))}
            {!data.length && (
              <tr>
                <td
                  colSpan={6}
                  className="py-6 text-center text-sm text-gray-500"
                >
                  No exports yet. Click Generate export to create one.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}

      <ExportDialog open={open} onClose={() => setOpen(false)} />
    </div>
  );
}
