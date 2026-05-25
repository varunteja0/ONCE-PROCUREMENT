import { cn } from "@/lib/cn";
import type { SubmissionStatus } from "@/types/api";

export interface StatusBadgeProps {
  status: SubmissionStatus;
  className?: string;
}

interface PillStyle {
  label: string;
  className: string;
}

const STATUS_STYLES: Record<SubmissionStatus, PillStyle> = {
  completed: {
    label: "Completed",
    className:
      "bg-emerald-100 text-emerald-800 ring-emerald-200 dark:bg-emerald-900/40 dark:text-emerald-200 dark:ring-emerald-800",
  },
  queued: {
    label: "Queued",
    className:
      "bg-amber-100 text-amber-800 ring-amber-200 dark:bg-amber-900/40 dark:text-amber-200 dark:ring-amber-800",
  },
  retrying: {
    label: "Retrying",
    className:
      "bg-amber-100 text-amber-800 ring-amber-200 dark:bg-amber-900/40 dark:text-amber-200 dark:ring-amber-800",
  },
  running: {
    label: "Running",
    className: "bg-sky-100 text-sky-800 ring-sky-200 dark:bg-sky-900/40 dark:text-sky-200 dark:ring-sky-800",
  },
  failed: {
    label: "Failed",
    className: "bg-rose-100 text-rose-800 ring-rose-200 dark:bg-rose-900/40 dark:text-rose-200 dark:ring-rose-800",
  },
  blocked: {
    label: "Blocked",
    className:
      "bg-purple-100 text-purple-800 ring-purple-200 dark:bg-purple-900/40 dark:text-purple-200 dark:ring-purple-800",
  },
  platform_unsupported: {
    label: "Unsupported",
    className: "bg-slate-200 text-slate-700 ring-slate-300 dark:bg-slate-700 dark:text-slate-200 dark:ring-slate-600",
  },
};

export function StatusBadge({ status, className }: StatusBadgeProps): JSX.Element {
  const style = STATUS_STYLES[status];
  return (
    <span
      role="status"
      aria-label={`Status: ${style.label}`}
      data-status={status}
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset",
        style.className,
        className,
      )}
    >
      {style.label}
    </span>
  );
}

export default StatusBadge;
