import { useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, RefreshCw } from 'lucide-react';
import {
  useSubmission,
  useSubmissionReceipt,
  useRetrySubmission,
} from '@/hooks/useSubmissions';
import {
  Button,
  Card,
  CardHeader,
  DateDisplay,
  ErrorState,
  Skeleton,
  StatusBadge,
} from '@/components/ui';
import ReceiptVerifierWidget from '@/components/ReceiptVerifierWidget';
import { toast } from '@/lib/toast';

const LIVE_STATUSES = new Set(['queued', 'running', 'retrying']);

export default function SubmissionDetail(): JSX.Element {
  const params = useParams<{ id: string }>();
  const navigate = useNavigate();
  const id = params.id;

  const detail = useSubmission(id);

  const receipt = useSubmissionReceipt(
    detail.data?.status === 'completed' ? id : undefined,
  );
  const retry = useRetrySubmission();

  const isLive = detail.data ? LIVE_STATUSES.has(detail.data.status) : false;
  useEffect(() => {
    if (!isLive) return undefined;
    const t = window.setInterval(() => {
      void detail.refetch();
    }, 2500);
    return () => window.clearInterval(t);
  }, [isLive, detail]);

  async function onRetry(): Promise<void> {
    if (!id) return;
    try {
      await retry.mutateAsync(id);
      toast.success('Submission requeued.');
    } catch (err) {
      toast.error(err, 'Retry failed');
    }
  }

  return (
    <div className="space-y-4">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => navigate('/submissions')}
        leadingIcon={<ArrowLeft className="h-3.5 w-3.5" />}
      >
        Back to submissions
      </Button>

      {detail.isLoading ? (
        <div className="space-y-3" aria-busy="true">
          <Skeleton className="h-7 w-64" />
          <Skeleton className="h-32 w-full" />
        </div>
      ) : detail.error || !detail.data ? (
        <ErrorState
          title="Submission not found"
          error={detail.error ?? new Error('Unknown')}
          onRetry={() => void detail.refetch()}
        />
      ) : (
        <>
          <header className="flex items-start justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
                Submission {detail.data.id.slice(0, 8)}
              </h1>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Supplier {detail.data.supplier_id.slice(0, 8)} · Portal{' '}
                {detail.data.portal_id.slice(0, 8)}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge status={detail.data.status} />
              {(detail.data.status === 'failed' ||
                detail.data.status === 'blocked') && (
                <Button
                  size="sm"
                  variant="outline"
                  loading={retry.isPending}
                  onClick={() => void onRetry()}
                  leadingIcon={<RefreshCw className="h-3.5 w-3.5" />}
                >
                  Retry
                </Button>
              )}
            </div>
          </header>

          <Card>
            <CardHeader title="Run details" />
            <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-xs text-slate-500 dark:text-slate-400">
                  Attempts
                </dt>
                <dd>{detail.data.attempt_count}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500 dark:text-slate-400">Created</dt>
                <dd>
                  <DateDisplay value={detail.data.created_at} />
                </dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500 dark:text-slate-400">Started</dt>
                <dd>
                  <DateDisplay value={detail.data.started_at} />
                </dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500 dark:text-slate-400">
                  Completed
                </dt>
                <dd>
                  <DateDisplay value={detail.data.completed_at} />
                </dd>
              </div>
            </dl>
            {detail.data.last_error ? (
              <div className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800 dark:border-rose-800 dark:bg-rose-950/30 dark:text-rose-200">
                <p className="font-medium">Last error</p>
                <p className="font-mono text-xs">{detail.data.last_error}</p>
              </div>
            ) : null}
          </Card>

          <Card padded={false}>
            <CardHeader title="Payload" />
            <pre className="max-h-72 overflow-auto rounded-b-lg bg-slate-900 p-4 text-xs text-slate-100">
              {JSON.stringify(detail.data.payload_json, null, 2)}
            </pre>
          </Card>

          {detail.data.result_json ? (
            <Card padded={false}>
              <CardHeader title="Result" />
              <pre className="max-h-72 overflow-auto rounded-b-lg bg-slate-50 p-4 text-xs text-slate-800 dark:bg-slate-800 dark:text-slate-100">
                {JSON.stringify(detail.data.result_json, null, 2)}
              </pre>
            </Card>
          ) : null}

          {detail.data.status === 'completed' && receipt.data ? (
            <Card>
              <CardHeader title="Receipt" />
              <ReceiptVerifierWidget receiptId={receipt.data.id} />
            </Card>
          ) : null}
        </>
      )}
    </div>
  );
}
