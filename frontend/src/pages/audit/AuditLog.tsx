// --- L3.10 audit ---
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuditList } from '@/hooks/useAudit';
import { AuditTimeline } from '@/components/audit/AuditTimeline';
import { ChainVerificationBadge } from '@/components/audit/ChainVerificationBadge';
import type { AuditActorType } from '@/services/auditApi';

export default function AuditLog() {
  const [actorType, setActorType] = useState<AuditActorType | ''>('');
  const [resourceType, setResourceType] = useState('');
  const params = useMemo(
    () => ({
      limit: 100,
      actor_type: actorType || undefined,
      resource_type: resourceType || undefined,
    }),
    [actorType, resourceType],
  );
  const { data, isLoading, isError, error } = useAuditList(params);

  return (
    <div className="space-y-4 p-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Audit log</h1>
        <div className="flex items-center gap-3">
          <ChainVerificationBadge />
          <Link
            to="/audit/exports"
            className="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-50"
          >
            Exports
          </Link>
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        <label className="flex items-center gap-2 text-sm">
          Actor
          <select
            value={actorType}
            onChange={(e) =>
              setActorType(e.target.value as AuditActorType | '')
            }
            className="rounded border border-gray-300 p-1 text-sm"
            data-testid="filter-actor"
          >
            <option value="">All</option>
            <option value="user">User</option>
            <option value="operator">Operator</option>
            <option value="system">System</option>
            <option value="inbound_email">Inbound email</option>
            <option value="webhook">Webhook</option>
            <option value="worker">Worker</option>
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm">
          Resource type
          <input
            value={resourceType}
            onChange={(e) => setResourceType(e.target.value)}
            placeholder="supplier, submission, …"
            className="rounded border border-gray-300 p-1 font-mono text-sm"
            data-testid="filter-resource"
          />
        </label>
      </div>

      {isLoading && <div className="text-sm text-gray-500">Loading…</div>}
      {isError && (
        <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
          {(error as Error).message}
        </div>
      )}
      {data && <AuditTimeline items={data.items} />}
      {data && (
        <div className="text-xs text-gray-500">
          Showing {data.items.length} of {data.total} events.
        </div>
      )}
    </div>
  );
}
