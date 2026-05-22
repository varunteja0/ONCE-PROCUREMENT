// --- L3.10 audit ---
import { Link } from 'react-router-dom';
import type { AuditLogRead } from '@/services/auditApi';

export interface AuditTimelineProps {
  items: AuditLogRead[];
  emptyMessage?: string;
}

const ACTOR_DOT: Record<string, string> = {
  user: 'bg-blue-500',
  operator: 'bg-amber-500',
  system: 'bg-slate-500',
  inbound_email: 'bg-purple-500',
  webhook: 'bg-cyan-500',
  worker: 'bg-emerald-500',
};

export function AuditTimeline({ items, emptyMessage }: AuditTimelineProps) {
  if (!items.length) {
    return (
      <div className="rounded border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
        {emptyMessage ?? 'No audit events yet.'}
      </div>
    );
  }
  return (
    <ol className="relative ml-3 border-l border-gray-200" data-testid="audit-timeline">
      {items.map((it) => {
        const dot = ACTOR_DOT[it.actor_type] ?? 'bg-gray-400';
        return (
          <li key={it.id} className="mb-4 ml-4">
            <span
              className={`absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full ${dot}`}
              aria-hidden
            />
            <Link
              to={`/audit/${it.id}`}
              className="block rounded border border-transparent p-2 hover:border-gray-200 hover:bg-gray-50"
            >
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-medium">
                  {it.actor_email ?? it.actor_id ?? it.actor_type}
                  <span className="ml-1 text-gray-500">{it.action_verb}</span>{' '}
                  <span className="font-mono text-xs text-gray-700">
                    {it.resource_type}
                    {it.resource_id ? `/${it.resource_id}` : ''}
                  </span>
                </span>
                <time
                  dateTime={it.occurred_at}
                  className="shrink-0 text-xs text-gray-500"
                >
                  {new Date(it.occurred_at).toLocaleString()}
                </time>
              </div>
              <div className="mt-0.5 truncate font-mono text-[10px] text-gray-400">
                #{it.chain_position} · {it.this_hash.slice(0, 16)}…
              </div>
            </Link>
          </li>
        );
      })}
    </ol>
  );
}

export default AuditTimeline;
