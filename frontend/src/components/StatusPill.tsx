import clsx from 'clsx';
import type { SubmissionStatus } from '@/services/api';

export interface StatusPillProps {
  status: SubmissionStatus;
  className?: string;
}

interface PillStyle {
  label: string;
  className: string;
}

const STATUS_STYLES: Record<SubmissionStatus, PillStyle> = {
  completed: {
    label: 'Completed',
    className: 'bg-emerald-100 text-emerald-800 ring-emerald-200',
  },
  queued: {
    label: 'Queued',
    className: 'bg-amber-100 text-amber-800 ring-amber-200',
  },
  retrying: {
    label: 'Retrying',
    className: 'bg-amber-100 text-amber-800 ring-amber-200',
  },
  running: {
    label: 'Running',
    className: 'bg-sky-100 text-sky-800 ring-sky-200',
  },
  failed: {
    label: 'Failed',
    className: 'bg-rose-100 text-rose-800 ring-rose-200',
  },
  blocked: {
    label: 'Blocked',
    className: 'bg-purple-100 text-purple-800 ring-purple-200',
  },
  platform_unsupported: {
    label: 'Unsupported',
    className: 'bg-slate-200 text-slate-700 ring-slate-300',
  },
};

export default function StatusPill({
  status,
  className,
}: StatusPillProps): JSX.Element {
  const style = STATUS_STYLES[status];
  return (
    <span
      role="status"
      aria-label={`Submission status: ${style.label}`}
      className={clsx(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset',
        style.className,
        className,
      )}
    >
      {style.label}
    </span>
  );
}
