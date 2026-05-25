// --- L3.10 audit ---
import { useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Download, FileText } from 'lucide-react';
import { useAuditList } from '@/hooks/useAudit';
import { AuditTimeline } from '@/components/audit/AuditTimeline';
import { ChainVerificationBadge } from '@/components/audit/ChainVerificationBadge';
import type { AuditActorType } from '@/services/auditApi';
import {
  Button,
  EmptyState,
  PaginationControls,
  Skeleton,
  Tooltip,
} from '@/components/ui';
import { downloadCsv, toCsv } from '@/lib/csv';
import { toast } from '@/lib/toast';

const PAGE_SIZE = 100;

const ACTOR_OPTIONS: ReadonlyArray<{ value: '' | AuditActorType; label: string }> = [
  { value: '', label: 'All' },
  { value: 'user', label: 'User' },
  { value: 'operator', label: 'Operator' },
  { value: 'system', label: 'System' },
  { value: 'inbound_email', label: 'Inbound email' },
  { value: 'webhook', label: 'Webhook' },
  { value: 'worker', label: 'Worker' },
];

const ALLOWED_ACTORS: ReadonlyArray<AuditActorType> = [
  'user',
  'operator',
  'system',
  'inbound_email',
  'webhook',
  'worker',
];

function parseActor(raw: string | null): '' | AuditActorType {
  if (!raw) return '';
  return (ALLOWED_ACTORS as ReadonlyArray<string>).includes(raw)
    ? (raw as AuditActorType)
    : '';
}

export default function AuditLog(): JSX.Element {
  const [params, setParams] = useSearchParams();
  const actorType = parseActor(params.get('actor'));
  const resourceType = params.get('resource') ?? '';
  const page = Math.max(1, Number(params.get('page') ?? '1'));

  const queryParams = useMemo(
    () => ({
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
      actor_type: actorType || undefined,
      resource_type: resourceType || undefined,
    }),
    [actorType, resourceType, page],
  );
  const { data, isLoading, isError, error } = useAuditList(queryParams);

  function patchParams(mutator: (p: URLSearchParams) => void): void {
    setParams((prev) => {
      const out = new URLSearchParams(prev);
      mutator(out);
      out.set('page', '1');
      return out;
    });
  }

  function setPage(next: number): void {
    setParams((prev) => {
      const out = new URLSearchParams(prev);
      out.set('page', String(next));
      return out;
    });
  }

  function exportCsv(): void {
    const items = data?.items ?? [];
    if (items.length === 0) {
      toast.error('Nothing to export.');
      return;
    }
    const csv = toCsv(items, [
      { header: 'Occurred at', value: (r) => r.occurred_at },
      { header: 'Chain position', value: (r) => r.chain_position },
      { header: 'Actor type', value: (r) => r.actor_type },
      { header: 'Actor email', value: (r) => r.actor_email ?? '' },
      { header: 'Action', value: (r) => r.action_verb },
      { header: 'Resource type', value: (r) => r.resource_type },
      { header: 'Resource ID', value: (r) => r.resource_id ?? '' },
      { header: 'Resource label', value: (r) => r.resource_label ?? '' },
    ]);
    downloadCsv(`audit-${new Date().toISOString().slice(0, 10)}.csv`, csv);
  }

  return (
    <div className="space-y-4 p-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
          Audit log
        </h1>
        <div className="flex items-center gap-3">
          <Tooltip label="Cryptographic audit chain verification">
            <span>
              <ChainVerificationBadge />
            </span>
          </Tooltip>
          <Button
            variant="outline"
            size="sm"
            onClick={exportCsv}
            disabled={(data?.items.length ?? 0) === 0}
            leadingIcon={<Download className="h-3.5 w-3.5" />}
          >
            Export CSV
          </Button>
          <Link
            to="/audit/exports"
            className="rounded border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800"
          >
            Exports
          </Link>
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
          Actor
          <select
            value={actorType}
            onChange={(e) =>
              patchParams((p) => {
                if (e.target.value === '') p.delete('actor');
                else p.set('actor', e.target.value);
              })
            }
            className="rounded border border-slate-300 bg-white p-1 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            data-testid="filter-actor"
          >
            {ACTOR_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
          Resource type
          <input
            value={resourceType}
            onChange={(e) =>
              patchParams((p) => {
                if (e.target.value === '') p.delete('resource');
                else p.set('resource', e.target.value);
              })
            }
            placeholder="supplier, submission, …"
            className="rounded border border-slate-300 bg-white p-1 font-mono text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            data-testid="filter-resource"
          />
        </label>
      </div>

      {isLoading && (
        <div className="space-y-2" aria-busy="true">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      )}
      {isError && (
        <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950/30 dark:text-red-300">
          {(error as Error).message}
        </div>
      )}
      {data && data.items.length === 0 && !isLoading ? (
        <EmptyState
          title="No audit events"
          description={
            actorType || resourceType
              ? 'No events match the selected filters.'
              : 'Audit events will appear as soon as your tenant performs any tracked action.'
          }
          icon={FileText}
        />
      ) : null}
      {data && data.items.length > 0 ? <AuditTimeline items={data.items} /> : null}
      {data && (
        <div className="text-xs text-slate-500 dark:text-slate-400">
          Showing {data.items.length} of {data.total} events.
        </div>
      )}

      <PaginationControls
        page={page}
        pageSize={PAGE_SIZE}
        total={data?.total ?? null}
        onPageChange={setPage}
        isLoading={isLoading}
      />
    </div>
  );
}
