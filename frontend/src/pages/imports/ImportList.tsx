// --- L3.7 imports ---
import { Link } from 'react-router-dom';
import { Upload, FileSpreadsheet } from 'lucide-react';
import { Button, EmptyState, ErrorState, Skeleton } from '@/components/ui';
import { useImportsList } from '@/hooks/useImports';
import type { ImportJobListItem, ImportStatus } from '@/services/importsApi';
import { extractErrorMessage } from '@/services/api';
import { cn } from '@/lib/cn';

const STATUS_CLASS: Record<ImportStatus, string> = {
  pending: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200',
  validating: 'bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-200',
  dry_run_ready: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200',
  importing: 'bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-200',
  completed: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200',
  failed: 'bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-200',
  canceled: 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-200',
};

function StatusPill({ status }: { status: ImportStatus }): JSX.Element {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
        STATUS_CLASS[status],
      )}
    >
      {status}
    </span>
  );
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function ImportList(): JSX.Element {
  const { data, isLoading, error, refetch } = useImportsList(50, 0, {
    refetchInterval: 5_000,
  });

  return (
    <div className="space-y-4 p-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Bulk Imports</h1>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Upload CSV or XLSX files of suppliers, COIs, loss runs, or producer
            licenses.
          </p>
        </div>
        <Link to="/imports/new">
          <Button>
            <Upload aria-hidden="true" className="mr-2 h-4 w-4" />
            New import
          </Button>
        </Link>
      </header>

      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : error ? (
        <ErrorState
          title="Could not load import jobs"
          description={extractErrorMessage(error)}
          onRetry={() => refetch()}
        />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          icon={FileSpreadsheet}
          title="No imports yet"
          description="Upload a spreadsheet to get started."
          action={{
            label: 'New import',
            onClick: () => {
              window.location.assign('/imports/new');
            },
          }}
        />
      ) : (
        <div className="overflow-x-auto rounded border border-gray-200 dark:border-gray-800">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500 dark:bg-gray-900">
              <tr>
                <th className="px-4 py-2">Filename</th>
                <th className="px-4 py-2">Entity</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2 text-right">Total</th>
                <th className="px-4 py-2 text-right">Valid</th>
                <th className="px-4 py-2 text-right">Invalid</th>
                <th className="px-4 py-2 text-right">Imported</th>
                <th className="px-4 py-2">Created</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {data.items.map((j: ImportJobListItem) => (
                <tr
                  key={j.id}
                  className="border-t border-gray-200 dark:border-gray-800"
                >
                  <td className="px-4 py-2 font-mono text-xs">
                    {j.original_filename}
                  </td>
                  <td className="px-4 py-2">{j.entity_type}</td>
                  <td className="px-4 py-2">
                    <StatusPill status={j.status} />
                  </td>
                  <td className="px-4 py-2 text-right font-mono">
                    {j.total_rows.toLocaleString()}
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-emerald-700 dark:text-emerald-300">
                    {j.valid_rows.toLocaleString()}
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-red-700 dark:text-red-300">
                    {j.invalid_rows.toLocaleString()}
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-blue-700 dark:text-blue-300">
                    {j.imported_rows.toLocaleString()}
                  </td>
                  <td className="px-4 py-2 text-xs">{formatDate(j.created_at)}</td>
                  <td className="px-4 py-2 text-right">
                    <Link
                      className="text-blue-600 hover:underline dark:text-blue-400"
                      to={`/imports/${j.id}`}
                    >
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
// --- /L3.7 imports ---
