import { ExternalLink, Receipt as ReceiptIcon } from "lucide-react";

import type { SubmissionListItem, SubmissionStatus } from "../../lib/api";

interface Props {
  submissions: SubmissionListItem[];
  appUrlBase?: string;
}

const STATUS_CLASS: Record<SubmissionStatus, string> = {
  queued: "pill-queued",
  running: "pill-running",
  completed: "pill-completed",
  failed: "pill-failed",
  retrying: "pill-running",
  blocked: "pill-blocked",
  platform_unsupported: "pill-failed",
};

export function Submissions({
  submissions,
  appUrlBase = "http://localhost:5173",
}: Props): JSX.Element {
  const top = submissions.slice(0, 10);

  return (
    <section className="p-3 space-y-3" aria-labelledby="subs-title">
      <h2
        id="subs-title"
        className="text-xs font-semibold uppercase tracking-wide text-slate-500"
      >
        Recent submissions
      </h2>

      {top.length === 0 ? (
        <div className="card p-4 text-center text-xs text-slate-500">
          <div className="mx-auto mb-2 h-8 w-8 rounded-full bg-slate-100 flex items-center justify-center">
            <ReceiptIcon className="h-4 w-4 text-slate-500" aria-hidden />
          </div>
          <div className="font-medium text-slate-700">No submissions yet</div>
          <div className="mt-0.5">They'll appear here after your first run.</div>
        </div>
      ) : (
        <ul className="space-y-2" role="list">
          {top.map((s) => (
            <Row key={s.id} submission={s} appUrlBase={appUrlBase} />
          ))}
        </ul>
      )}
    </section>
  );
}

function Row({
  submission,
  appUrlBase,
}: {
  submission: SubmissionListItem;
  appUrlBase: string;
}): JSX.Element {
  const url = `${appUrlBase.replace(/\/+$/, "")}/submissions/${submission.id}`;
  const onOpen = (): void => {
    try {
      if (typeof chrome !== "undefined" && chrome.tabs?.create) {
        void chrome.tabs.create({ url });
      } else if (typeof window !== "undefined") {
        window.open(url, "_blank", "noopener,noreferrer");
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
            <span className={STATUS_CLASS[submission.status]}>
              {submission.status}
            </span>
            <span className="text-[10px] text-slate-500">
              {formatRelative(submission.updated_at)}
            </span>
          </div>
          <div
            className="mt-1 text-xs font-mono text-slate-700 truncate"
            title={submission.id}
          >
            #{submission.id.slice(0, 8)}
          </div>
          <div className="text-[10px] text-slate-500 truncate">
            supplier {submission.supplier_id.slice(0, 8)}
          </div>
        </div>
        <button
          type="button"
          className="btn-secondary h-7 px-2 text-[11px]"
          onClick={onOpen}
          aria-label={`Open submission ${submission.id.slice(0, 8)} in the web app`}
        >
          <ExternalLink className="h-3.5 w-3.5" aria-hidden />
        </button>
      </div>
    </li>
  );
}

function formatRelative(iso: string): string {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return iso;
  const s = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}
