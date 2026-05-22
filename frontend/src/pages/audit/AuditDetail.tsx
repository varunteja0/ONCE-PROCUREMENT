// --- L3.10 audit ---
import { Link, useParams } from 'react-router-dom';
import { useAuditEntry } from '@/hooks/useAudit';

export default function AuditDetail() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, isError, error } = useAuditEntry(id);

  if (isLoading)
    return <div className="p-4 text-sm text-gray-500">Loading…</div>;
  if (isError)
    return (
      <div className="m-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
        {(error as Error).message}
      </div>
    );
  if (!data) return null;

  return (
    <div className="space-y-4 p-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">
          {data.action_verb} {data.resource_type}
          {data.resource_id ? ` · ${data.resource_id}` : ''}
        </h1>
        <Link to="/audit" className="text-sm text-blue-700 hover:underline">
          ← Back to audit log
        </Link>
      </div>

      <dl className="grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
        <Field label="ID" value={data.id} mono />
        <Field
          label="Occurred at"
          value={new Date(data.occurred_at).toLocaleString()}
        />
        <Field label="Actor type" value={data.actor_type} />
        <Field
          label="Actor"
          value={data.actor_email ?? data.actor_id ?? '—'}
        />
        <Field label="Request ID" value={data.request_id ?? '—'} mono />
        <Field label="IP" value={data.ip ?? '—'} mono />
        <Field label="User agent" value={data.user_agent ?? '—'} />
        <Field label="Chain position" value={String(data.chain_position)} />
        <Field label="prev_hash" value={data.prev_hash} mono wrap />
        <Field label="this_hash" value={data.this_hash} mono wrap />
      </dl>

      <section>
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-600">
          Payload summary
        </h2>
        <pre
          data-testid="payload-summary"
          className="max-h-96 overflow-auto rounded border border-gray-200 bg-gray-50 p-3 font-mono text-xs"
        >
          {JSON.stringify(data.payload_summary ?? {}, null, 2)}
        </pre>
      </section>
    </div>
  );
}

function Field({
  label,
  value,
  mono,
  wrap,
}: {
  label: string;
  value: string;
  mono?: boolean;
  wrap?: boolean;
}) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-gray-500">{label}</dt>
      <dd
        className={`${mono ? 'font-mono' : ''} ${wrap ? 'break-all' : 'truncate'} text-sm`}
      >
        {value}
      </dd>
    </div>
  );
}
