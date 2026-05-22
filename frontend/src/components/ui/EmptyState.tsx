import type { ComponentType, ReactNode } from 'react';
import { Inbox, type LucideProps } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/cn';

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

export function EmptyState({
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
      className={cn(
        'flex flex-col items-center justify-center rounded-lg border border-dashed border-slate-300 bg-white px-6 py-12 text-center dark:border-slate-700 dark:bg-slate-900',
        className,
      )}
    >
      <div
        aria-hidden="true"
        className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400"
      >
        <Icon className="h-6 w-6" aria-hidden="true" />
      </div>
      <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
        {title}
      </h3>
      {description ? (
        <div className="mt-1 max-w-md text-sm text-slate-600 dark:text-slate-400">
          {description}
        </div>
      ) : null}
      {action ? (
        <Button variant="primary" size="md" onClick={action.onClick} className="mt-5">
          {action.label}
        </Button>
      ) : null}
    </div>
  );
}

export default EmptyState;
