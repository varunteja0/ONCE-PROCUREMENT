import { useState } from "react";
import { CheckCircle2, Loader2, RefreshCw, Users } from "lucide-react";

import { send } from "../../lib/messaging";
import { usePopupStore, selectActiveSupplier } from "../../lib/store";
import type { SupplierListItem } from "../../lib/api";

interface Props {
  suppliers: SupplierListItem[];
  onRefreshed: (next: SupplierListItem[]) => void;
}

export function Suppliers({ suppliers, onRefreshed }: Props): JSX.Element {
  const tabId = usePopupStore((s) => s.tabId);
  const active = usePopupStore(selectActiveSupplier);
  const setActive = usePopupStore((s) => s.setActiveSupplier);
  const setBanner = usePopupStore((s) => s.setBanner);

  const [refreshing, setRefreshing] = useState(false);

  const onRefresh = async (): Promise<void> => {
    setRefreshing(true);
    try {
      const resp = await send({ type: "sync.now" });
      if (!resp.ok) {
        setBanner({ kind: "error", text: `Sync failed: ${resp.error}` });
        return;
      }
      const { getCachedSuppliers } = await import("../../lib/sync");
      onRefreshed(await getCachedSuppliers());
      setBanner({
        kind: "success",
        text: `Synced ${resp.supplier_count} suppliers.`,
      });
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <section className="p-3 space-y-3" aria-labelledby="suppliers-title">
      <div className="flex items-center justify-between">
        <h2
          id="suppliers-title"
          className="text-xs font-semibold uppercase tracking-wide text-slate-500"
        >
          Suppliers
        </h2>
        <button
          type="button"
          className="btn-ghost h-6 px-1.5 text-xs"
          onClick={() => void onRefresh()}
          disabled={refreshing}
          title="Refresh"
          aria-label="Refresh suppliers"
        >
          {refreshing ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
          ) : (
            <RefreshCw className="h-3.5 w-3.5" aria-hidden />
          )}
        </button>
      </div>

      {suppliers.length === 0 ? (
        <div className="card p-4 text-center text-xs text-slate-500">
          <div className="mx-auto mb-2 h-8 w-8 rounded-full bg-slate-100 flex items-center justify-center">
            <Users className="h-4 w-4 text-slate-500" aria-hidden />
          </div>
          <div className="font-medium text-slate-700">No suppliers yet</div>
          <div className="mt-0.5">Tap refresh to pull from your backend.</div>
        </div>
      ) : (
        <ul className="space-y-1.5" role="list">
          {suppliers.map((s) => {
            const isActive = s.id === active;
            return (
              <li key={s.id}>
                <button
                  type="button"
                  className={`w-full text-left card p-2.5 transition-colors ${
                    isActive ? "ring-2 ring-brand-500 border-brand-300" : "hover:bg-slate-50"
                  }`}
                  aria-pressed={isActive}
                  onClick={() => {
                    if (tabId !== null) setActive(tabId, s.id);
                  }}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <div className="text-xs font-medium truncate">{s.legal_name}</div>
                      {s.dba_name ? (
                        <div className="text-[10px] text-slate-500 truncate">
                          dba {s.dba_name}
                        </div>
                      ) : null}
                    </div>
                    {isActive ? (
                      <CheckCircle2
                        className="h-4 w-4 text-brand-600 flex-shrink-0"
                        aria-label="Active for this tab"
                      />
                    ) : null}
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
