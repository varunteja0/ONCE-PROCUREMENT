// --- L3.7 imports ---
import type { ImportRowError } from '@/services/importsApi';

export interface PreviewTableProps {
  errors: ImportRowError[];
  /** Total error count from server (preview may be capped at 50). */
  totalErrors: number;
  /** Optional CSV download URL for the full error report. */
  errorsCsvUrl?: string;
}

export function PreviewTable({
  errors,
  totalErrors,
  errorsCsvUrl,
}: PreviewTableProps): JSX.Element {
  if (errors.length === 0) {
    return (
      <p className="rounded border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900 dark:border-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-200">
        No validation errors — all rows look good.
      </p>
    );
  }
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span>
          Showing {errors.length} of {totalErrors.toLocaleString()} validation
          {totalErrors === 1 ? ' error' : ' errors'}.
        </span>
        {errorsCsvUrl ? (
          <a
            href={errorsCsvUrl}
            className="text-blue-600 hover:underline dark:text-blue-400"
            download
          >
            Download full report (CSV)
          </a>
        ) : null}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase text-gray-500">
            <tr>
              <th className="py-2 pr-4">Row</th>
              <th className="py-2 pr-4">Column</th>
              <th className="py-2 pr-4">Value</th>
              <th className="py-2 pr-4">Code</th>
              <th className="py-2">Message</th>
            </tr>
          </thead>
          <tbody>
            {errors.map((e, idx) => (
              <tr
                key={`${e.row_number}-${e.column ?? ''}-${idx}`}
                className="border-t border-gray-200 dark:border-gray-800"
              >
                <td className="py-2 pr-4 font-mono">{e.row_number}</td>
                <td className="py-2 pr-4 font-mono">{e.column ?? '—'}</td>
                <td className="py-2 pr-4 max-w-[20ch] truncate" title={e.value ?? ''}>
                  {e.value ?? '—'}
                </td>
                <td className="py-2 pr-4">
                  <code className="rounded bg-gray-100 px-1 text-xs dark:bg-gray-800">
                    {e.error_code}
                  </code>
                </td>
                <td className="py-2">{e.error_message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default PreviewTable;
// --- /L3.7 imports ---
