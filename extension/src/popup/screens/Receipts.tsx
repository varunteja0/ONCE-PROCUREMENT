/**
 * Receipts screen — lists the most recent signed submission receipts
 * for the active tenant. Mirrors the look/feel of `Submissions` so the
 * popup stays cohesive. Data is pulled from the backend on mount; we
 * also surface a "Verify" link to the public verifier.
 */
import { useEffect, useState } from "react";
import { ExternalLink, Loader2, Receipt as ReceiptIcon } from "lucide-react";

import { listReceipts, type ReceiptListItem } from "../../lib/api";

interface Props {
  appUrlBase?: string;
}

export function Receipts({
  appUrlBase = "http://localhost:5173",
}: Props): JSX.Element {
  const [items, setItems] = useState<ReceiptListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async (): Promise<void> => {
      try {
        const list = await listReceipts();
        if (!cancelled) setItems(list);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "load_failed");
          setItems([]);
        }
      }
    })();
    return (): void => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="p-3 space-y-3" aria-labelledby="rcpt-title">
      <h2
        id="rcpt-title"
        className="text-xs font-semibold uppercase tracking-wide text-slate-500"
      >
        Recent receipts
      </h2>

      {items === null ? (
        <div className="card p-4 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> Loading…
        </div>
      ) : items.length === 0 ? (
        <div className="card p-4 text-center text-xs text-slate-500">
          <div className="mx-auto mb-2 h-8 w-8 rounded-full bg-slate-100 flex items-center justify-center">
            <ReceiptIcon className="h-4 w-4 text-slate-500" aria-hidden />
          </div>
          <div className="font-medium text-slate-700">No receipts yet</div>
          <div className="mt-0.5">
            {error ?? "Captured submissions will produce signed receipts here."}
          </div>
        </div>
      ) : (
        <ul className="space-y-2" role="list">
          {items.slice(0, 10).map((r) => (
            <Row key={r.id} receipt={r} appUrlBase={appUrlBase} />
          ))}
        </ul>
      )}
    </section>
  );
}

function Row({
  receipt,
  appUrlBase,
}: {
  receipt: ReceiptListItem;
  appUrlBase: string;
}): JSX.Element {
  const verifyUrl =
    receipt.verify_url ??
    `${appUrlBase.replace(/\/+$/, "")}/verify/${receipt.id}`;

  const onOpen = (): void => {
    try {
      if (typeof chrome !== "undefined" && chrome.tabs?.create) {
        void chrome.tabs.create({ url: verifyUrl });
      } else if (typeof window !== "undefined") {
        window.open(verifyUrl, "_blank", "noopener,noreferrer");
      }
    } catch {
      /* ignore */
    }
  };

  return (
    <li className="card p-2.5">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-wide font-semibold text-slate-700">
              {receipt.portal_platform}
            </span>
            <span className="text-[10px] text-slate-500">
              {new Date(receipt.submitted_at).toLocaleString()}
            </span>
          </div>
          <div
            className="mt-1 text-xs font-mono text-slate-700 truncate"
            title={receipt.id}
          >
            #{receipt.id.slice(0, 8)}
          </div>
          <div className="text-[10px] text-slate-500 truncate">
            sub {receipt.submission_id.slice(0, 8)}
          </div>
        </div>
        <button
          type="button"
          className="btn-secondary h-7 px-2 text-[11px]"
          onClick={onOpen}
          aria-label={`Verify receipt ${receipt.id.slice(0, 8)}`}
        >
          <ExternalLink className="h-3 w-3" aria-hidden /> Verify
        </button>
      </div>
    </li>
  );
}
