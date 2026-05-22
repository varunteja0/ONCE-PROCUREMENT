// --- L3.7 imports ---
import type { ImportJob, ImportJobDetail } from '@/services/importsApi';

export interface ImportProgressProps {
  job: ImportJob | ImportJobDetail;
}

function pct(num: number, denom: number): number {
  if (denom <= 0) return 0;
  return Math.min(100, Math.max(0, Math.round((num / denom) * 100)));
}

const STATUS_LABEL: Record<ImportJob['status'], string> = {
  pending: 'Pending',
  validating: 'Validating',
  dry_run_ready: 'Dry-run ready',
  importing: 'Importing',
  completed: 'Completed',
  failed: 'Failed',
  canceled: 'Canceled',
};

export function ImportProgress({ job }: ImportProgressProps): JSX.Element {
  const importingDone = job.status === 'completed' || job.status === 'importing';
  const percent = importingDone
    ? pct(job.imported_rows, Math.max(job.valid_rows, 1))
    : pct(job.valid_rows + job.invalid_rows, Math.max(job.total_rows, 1));

  return (
    <section aria-label="Import progress" className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium">{STATUS_LABEL[job.status]}</span>
        <span className="text-gray-600 dark:text-gray-400">{percent}%</span>
      </div>
      <div
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        className="h-2 w-full overflow-hidden rounded bg-gray-200 dark:bg-gray-800"
      >
        <div
          className={
            job.status === 'failed'
              ? 'h-full bg-red-500'
              : job.status === 'canceled'
                ? 'h-full bg-gray-500'
                : 'h-full bg-blue-600'
          }
          style={{ width: `${percent}%` }}
        />
      </div>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs text-gray-600 dark:text-gray-400 sm:grid-cols-4">
        <div>
          <dt>Total rows</dt>
          <dd className="font-mono text-sm text-gray-900 dark:text-gray-100">
            {job.total_rows.toLocaleString()}
          </dd>
        </div>
        <div>
          <dt>Valid</dt>
          <dd className="font-mono text-sm text-emerald-700 dark:text-emerald-300">
            {job.valid_rows.toLocaleString()}
          </dd>
        </div>
        <div>
          <dt>Invalid</dt>
          <dd className="font-mono text-sm text-red-700 dark:text-red-300">
            {job.invalid_rows.toLocaleString()}
          </dd>
        </div>
        <div>
          <dt>Imported</dt>
          <dd className="font-mono text-sm text-blue-700 dark:text-blue-300">
            {job.imported_rows.toLocaleString()}
          </dd>
        </div>
      </dl>
      {job.last_error ? (
        <p role="alert" className="text-sm text-red-700 dark:text-red-300">
          {job.last_error}
        </p>
      ) : null}
    </section>
  );
}

export default ImportProgress;
// --- /L3.7 imports ---
