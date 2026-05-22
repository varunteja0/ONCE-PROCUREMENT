import { AlertTriangle, CheckCircle2, ExternalLink } from 'lucide-react';
import type { Portal } from '@/services/api';

export interface PortalCardProps {
  portal: Portal;
  onSelect?: (portal: Portal) => void;
  className?: string;
}

function brandInitials(name: string): string {
  const trimmed = name.trim();
  if (!trimmed) return '·';
  const parts = trimmed.split(/\s+/).slice(0, 2);
  return parts.map((p) => p[0]?.toUpperCase() ?? '').join('') || trimmed[0]!.toUpperCase();
}

export default function PortalCard({
  portal,
  onSelect,
  className,
}: PortalCardProps): JSX.Element {
  const isInteractive = onSelect !== undefined;
  const baseClass = [
    'group relative flex w-full flex-col gap-3 rounded-lg border border-slate-200 bg-white p-4 text-left shadow-sm transition',
    isInteractive ? 'hover:border-slate-300 hover:shadow' : '',
    className ?? '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={baseClass}>
      <div className="flex items-center gap-3">
        <div
          aria-hidden="true"
          className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-slate-900 text-sm font-semibold text-white"
        >
          {brandInitials(portal.display_name)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="truncate text-sm font-semibold text-slate-900">
              {portal.display_name}
            </h3>
            {portal.is_supported ? (
              <span
                className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-medium text-emerald-800 ring-1 ring-inset ring-emerald-200"
                aria-label="Portal is supported"
              >
                <CheckCircle2 aria-hidden="true" className="h-3 w-3" />
                Supported
              </span>
            ) : (
              <span
                className="inline-flex items-center gap-1 rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-medium text-slate-700 ring-1 ring-inset ring-slate-300"
                aria-label="Portal is not supported"
              >
                Unsupported
              </span>
            )}
            {portal.risky ? (
              <span
                className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-800 ring-1 ring-inset ring-amber-200"
                aria-label="Portal flagged as risky"
              >
                <AlertTriangle aria-hidden="true" className="h-3 w-3" />
                Risky
              </span>
            ) : null}
          </div>
          <p className="truncate text-xs text-slate-500">{portal.platform}</p>
        </div>
      </div>

      {portal.notes ? (
        <p className="text-xs leading-relaxed text-slate-600">
          <span className="font-medium text-slate-700">ToS notes: </span>
          {portal.notes}
        </p>
      ) : (
        <p className="text-xs italic text-slate-400">
          No ToS notes on file for this portal.
        </p>
      )}

      <div className="mt-auto flex items-center justify-between gap-3 pt-1">
        {portal.base_url ? (
          <a
            href={portal.base_url}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-1 text-xs font-medium text-slate-600 hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2"
            aria-label={`Open ${portal.display_name} in a new tab`}
          >
            <ExternalLink aria-hidden="true" className="h-3 w-3" />
            <span className="truncate">{portal.base_url}</span>
          </a>
        ) : (
          <span />
        )}
        {isInteractive ? (
          <button
            type="button"
            onClick={() => onSelect?.(portal)}
            aria-label={`Select portal ${portal.display_name}`}
            className="inline-flex items-center rounded-md bg-slate-900 px-2.5 py-1.5 text-xs font-medium text-white transition hover:bg-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2"
          >
            Select
          </button>
        ) : null}
      </div>
    </div>
  );
}
