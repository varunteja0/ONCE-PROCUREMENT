// --- L3.9 inbound ---
import { Link, useParams } from 'react-router-dom';
import { Button, ErrorState, Skeleton } from '@/components/ui';
import {
  useInboundEmail,
  useQuarantineInbound,
  useRetryInbound,
} from '@/hooks/useInbound';
import { AttachmentList } from '@/components/inbound/AttachmentList';
import { RoutingResultBadge } from '@/components/inbound/RoutingResultBadge';
import { extractErrorMessage } from '@/services/api';

export default function InboundDetail(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, error, refetch } = useInboundEmail(id);
  const retry = useRetryInbound();
  const quarantine = useQuarantineInbound();

  if (isLoading) {
    return (
      <div className="space-y-3 p-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (error || !data) {
    return (
      <div className="p-6">
        <ErrorState
          title="Couldn't load email"
          description={error ? extractErrorMessage(error) : 'Not found.'}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <header className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <Link to="/inbound" className="text-xs text-sky-700 hover:underline dark:text-sky-300">
            ← Back to inbound
          </Link>
          <h1 className="mt-1 truncate text-2xl font-semibold">
            {data.subject ?? '(no subject)'}
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            From <span className="font-medium">{data.from_address}</span> ·{' '}
            {new Date(data.received_at).toLocaleString()}
          </p>
        </div>
        <div className="flex flex-shrink-0 items-center gap-2">
          <RoutingResultBadge status={data.status} />
          <Button
            variant="secondary"
            disabled={retry.isPending}
            onClick={() => retry.mutate(data.id)}
          >
            Retry routing
          </Button>
          <Button
            variant="secondary"
            disabled={quarantine.isPending}
            onClick={() => quarantine.mutate(data.id)}
          >
            Quarantine
          </Button>
        </div>
      </header>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <h2 className="text-sm font-semibold uppercase text-gray-500">Metadata</h2>
          <dl className="space-y-1 text-sm">
            <div className="flex gap-2">
              <dt className="w-32 text-gray-500">To</dt>
              <dd className="truncate">{data.to_address}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="w-32 text-gray-500">Message-ID</dt>
              <dd className="truncate font-mono text-xs">{data.message_id}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="w-32 text-gray-500">Spam score</dt>
              <dd>{data.spam_score?.toFixed(2) ?? '—'}</dd>
            </div>
            {data.draft_submission_id ? (
              <div className="flex gap-2">
                <dt className="w-32 text-gray-500">Submission</dt>
                <dd>
                  <Link
                    to={`/submissions/${data.draft_submission_id}`}
                    className="text-sky-700 hover:underline dark:text-sky-300"
                  >
                    {data.draft_submission_id.slice(0, 8)}…
                  </Link>
                </dd>
              </div>
            ) : null}
            {data.routing_error ? (
              <div className="flex gap-2">
                <dt className="w-32 text-gray-500">Error</dt>
                <dd className="text-rose-700 dark:text-rose-300">{data.routing_error}</dd>
              </div>
            ) : null}
          </dl>
        </div>
        <div className="space-y-2">
          <h2 className="text-sm font-semibold uppercase text-gray-500">Attachments</h2>
          <AttachmentList attachments={data.attachments} />
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase text-gray-500">Body</h2>
        <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-md border border-gray-200 bg-gray-50 p-3 text-sm dark:border-gray-700 dark:bg-gray-900">
          {data.raw_body_text ?? '(no plain-text body)'}
        </pre>
      </section>
    </div>
  );
}
