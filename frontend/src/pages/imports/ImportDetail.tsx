// --- L3.7 imports ---
import { useParams, Link } from 'react-router-dom';
import { Button, ErrorState, Skeleton } from '@/components/ui';
import { extractErrorMessage } from '@/services/api';
import {
  useImport,
  useCommitImport,
  useCancelImport,
} from '@/hooks/useImports';
import { importsApi } from '@/services/importsApi';
import { ImportProgress } from '@/components/imports/ImportProgress';
import { PreviewTable } from '@/components/imports/PreviewTable';

const ACTIVE_STATUSES = new Set(['validating', 'importing']);

export default function ImportDetail(): JSX.Element {
  const { id = '' } = useParams<{ id: string }>();
  const detailQ = useImport(id, { refetchInterval: 1500 });
  const commit = useCommitImport();
  const cancel = useCancelImport();

  const job = detailQ.data;
  const isActive = job ? ACTIVE_STATUSES.has(job.status) : false;
  const canCommit = job?.status === 'dry_run_ready' && job.valid_rows > 0;
  const canCancel = job && !['completed', 'failed', 'canceled'].includes(job.status);

  if (detailQ.isLoading && !job) {
    return (
      <div className="space-y-3 p-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (detailQ.error || !job) {
    return (
      <div className="p-6">
        <ErrorState
          title="Could not load import job"
          description={
            detailQ.error
              ? extractErrorMessage(detailQ.error)
              : 'Job not found.'
          }
          onRetry={() => detailQ.refetch()}
        />
      </div>
    );
  }

  return (
    <div className="space-y-4 p-6">
      <nav className="text-sm">
        <Link
          to="/imports"
          className="text-blue-600 hover:underline dark:text-blue-400"
        >
          ← All imports
        </Link>
      </nav>

      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">{job.original_filename}</h1>
        <p className="text-xs text-gray-500">
          <span className="font-mono">{job.id}</span> · entity{' '}
          <span className="font-mono">{job.entity_type}</span>
        </p>
      </header>

      <section className="rounded border border-gray-200 p-4 dark:border-gray-800">
        <ImportProgress job={job} />
      </section>

      <section className="space-y-3 rounded border border-gray-200 p-4 dark:border-gray-800">
        <h2 className="text-lg font-medium">Validation errors</h2>
        <PreviewTable
          errors={job.errors_preview}
          totalErrors={job.error_count}
          errorsCsvUrl={
            job.error_count > 0 ? importsApi.errorsUrl(job.id) : undefined
          }
        />
      </section>

      <div className="flex flex-wrap justify-end gap-2">
        {canCancel ? (
          <Button
            variant="outline"
            loading={cancel.isPending}
            onClick={() => void cancel.mutateAsync(job.id)}
          >
            Cancel import
          </Button>
        ) : null}
        {canCommit ? (
          <Button
            loading={commit.isPending}
            onClick={() => void commit.mutateAsync(job.id)}
          >
            Commit {job.valid_rows.toLocaleString()} rows
          </Button>
        ) : null}
      </div>

      {(commit.error || cancel.error) && (
        <p role="alert" className="text-sm text-red-700 dark:text-red-300">
          {extractErrorMessage(commit.error ?? cancel.error)}
        </p>
      )}

      {isActive ? (
        <p className="text-xs text-gray-500" aria-live="polite">
          Auto-refreshing every 1.5 s…
        </p>
      ) : null}
    </div>
  );
}
// --- /L3.7 imports ---
