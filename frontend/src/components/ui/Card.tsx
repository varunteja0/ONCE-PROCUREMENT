import type { HTMLAttributes, ReactNode } from 'react';
import { cn } from '@/lib/cn';

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  padded?: boolean;
}

export function Card({
  padded = true,
  className,
  ...rest
}: CardProps): JSX.Element {
  return (
    <div
      className={cn(
        'rounded-lg border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900',
        padded && 'p-4',
        className,
      )}
      {...rest}
    />
  );
}

export interface CardHeaderProps {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
}

export function CardHeader({
  title,
  description,
  actions,
  className,
}: CardHeaderProps): JSX.Element {
  return (
    <div
      className={cn(
        'flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 px-5 py-3 dark:border-slate-800',
        className,
      )}
    >
      <div className="min-w-0">
        <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
          {title}
        </h2>
        {description ? (
          <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 gap-2">{actions}</div> : null}
    </div>
  );
}
