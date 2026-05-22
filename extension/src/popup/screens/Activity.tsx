import { useEffect, useState } from "react";
import {
  AlertTriangle,
  Camera,
  Lock,
  RefreshCw,
  Send,
  Unlock,
} from "lucide-react";

import { send } from "../../lib/messaging";
import type { ActivityEntry } from "../../lib/messaging";

const ICONS = {
  fill: Send,
  capture: Camera,
  sync: RefreshCw,
  unlock: Unlock,
  lock: Lock,
  error: AlertTriangle,
} as const;

export function Activity(): JSX.Element {
  const [items, setItems] = useState<ActivityEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      try {
        const resp = await send({ type: "activity.list", limit: 20 });
        if (resp.ok) setItems(resp.items);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <section className="p-3 space-y-2" aria-labelledby="activity-title">
      <h2
        id="activity-title"
        className="text-xs font-semibold uppercase tracking-wide text-slate-500"
      >
        Recent activity
      </h2>
      {loading ? (
        <div className="text-[11px] text-slate-500 py-2">Loading…</div>
      ) : items.length === 0 ? (
        <div className="card p-3 text-center text-xs text-slate-500">
          No activity yet.
        </div>
      ) : (
        <ul className="space-y-1" role="list">
          {items.map((e) => {
            const Icon = ICONS[e.kind] ?? AlertTriangle;
            return (
              <li key={e.id} className="flex items-start gap-2 text-[11px] py-1">
                <Icon
                  className="h-3.5 w-3.5 text-slate-500 mt-0.5 flex-shrink-0"
                  aria-hidden
                />
                <div className="min-w-0 flex-1">
                  <div className="text-slate-700 truncate" title={e.detail}>
                    {e.detail}
                  </div>
                  <div className="text-[10px] text-slate-400">
                    {new Date(e.ts).toLocaleString(undefined, {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                    {e.portal ? ` · ${e.portal}` : ""}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
