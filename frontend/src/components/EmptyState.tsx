import type { ComponentType, ReactNode } from 'react';
import { Inbox, type LucideProps } from 'lucide-react';

export interface EmptyStateAction {
  label: string;
  onClick: () => void;
}

export interface EmptyStateProps {
  title: string;
  description?: ReactNode;
  icon?: ComponentType<LucideProps>;
  action?: EmptyStateAction;
  className?: string;
}

export default function EmptyState({
  title,
  description,
  icon: Icon = Inbox,
  action,
  className,
}: EmptyStateProps): JSX.Element {
  return (
    <div
      role="status"
      aria-live="polite"
      className={[
        'flex flex-col items-center justify-center rounded-lg border border-dashed border-slate-300 bg-white px-6 py-12 text-center',
        className ?? '',
      ]
        .filter(Boolean)
        .join(' ')}
    >
      <div
        aria-hidden="true"
        className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-500"
      >
        <Icon className="h-6 w-6" aria-hidden="true" />
      </div>
      <h3 className="text-base font-semibold text-slate-900">{title}</h3>
      {description ? (
        <div className="mt-1 max-w-md text-sm text-slate-600">{description}</div>
      ) : null}
      {action ? (
        <button
          type="button"
          onClick={action.onClick}
          className="mt-5 inline-flex items-center rounded-md bg-slate-900 px-3.5 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2"
        >
          {action.label}
        </button>
      ) : null}
    </div>
  );
}
