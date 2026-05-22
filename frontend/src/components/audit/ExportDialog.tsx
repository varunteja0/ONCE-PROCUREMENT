// --- L3.10 audit ---
import { useState } from 'react';
import { useCreateAuditExport } from '@/hooks/useAudit';
import type { AuditExportScope } from '@/services/auditApi';

export interface ExportDialogProps {
  open: boolean;
  onClose: () => void;
  onCreated?: (exportId: string) => void;
}

export function ExportDialog({ open, onClose, onCreated }: ExportDialogProps) {
  const [scope, setScope] = useState<AuditExportScope>('tenant');
  const [supplierId, setSupplierId] = useState('');
  const [submissionId, setSubmissionId] = useState('');
  const [since, setSince] = useState('');
  const [until, setUntil] = useState('');
  const mutation = useCreateAuditExport();

  if (!open) return null;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const params: Record<string, unknown> = {};
    if (scope === 'supplier') params.supplier_id = supplierId;
    if (scope === 'submission') params.submission_id = submissionId;
    if (scope === 'date_range') {
      params.since = since;
      params.until = until;
    }
    const result = await mutation.mutateAsync({
      scope,
      scope_params: params,
    });
    onCreated?.(result.id);
    onClose();
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Generate audit export"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
    >
      <form
        onSubmit={submit}
        className="w-full max-w-md rounded-lg bg-white p-6 shadow-lg"
      >
        <h2 className="mb-4 text-lg font-semibold">
          Generate signed audit export
        </h2>
        <label className="mb-3 block">
          <span className="mb-1 block text-sm font-medium">Scope</span>
          <select
            value={scope}
            onChange={(e) => setScope(e.target.value as AuditExportScope)}
            className="w-full rounded border border-gray-300 p-2"
          >
            <option value="tenant">Entire tenant</option>
            <option value="supplier">Single supplier</option>
            <option value="submission">Single submission</option>
            <option value="date_range">Date range</option>
          </select>
        </label>
        {scope === 'supplier' && (
          <label className="mb-3 block">
            <span className="mb-1 block text-sm font-medium">Supplier ID</span>
            <input
              required
              value={supplierId}
              onChange={(e) => setSupplierId(e.target.value)}
              className="w-full rounded border border-gray-300 p-2 font-mono text-sm"
            />
          </label>
        )}
        {scope === 'submission' && (
          <label className="mb-3 block">
            <span className="mb-1 block text-sm font-medium">Submission ID</span>
            <input
              required
              value={submissionId}
              onChange={(e) => setSubmissionId(e.target.value)}
              className="w-full rounded border border-gray-300 p-2 font-mono text-sm"
            />
          </label>
        )}
        {scope === 'date_range' && (
          <>
            <label className="mb-3 block">
              <span className="mb-1 block text-sm font-medium">Since</span>
              <input
                type="datetime-local"
                required
                value={since}
                onChange={(e) => setSince(e.target.value)}
                className="w-full rounded border border-gray-300 p-2"
              />
            </label>
            <label className="mb-3 block">
              <span className="mb-1 block text-sm font-medium">Until</span>
              <input
                type="datetime-local"
                required
                value={until}
                onChange={(e) => setUntil(e.target.value)}
                className="w-full rounded border border-gray-300 p-2"
              />
            </label>
          </>
        )}
        {mutation.isError && (
          <div className="mb-3 rounded border border-red-300 bg-red-50 p-2 text-sm text-red-700">
            {(mutation.error as Error).message}
          </div>
        )}
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-gray-300 px-3 py-1.5 text-sm"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={mutation.isPending}
            className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-60"
          >
            {mutation.isPending ? 'Queuing…' : 'Generate'}
          </button>
        </div>
      </form>
    </div>
  );
}

export default ExportDialog;
