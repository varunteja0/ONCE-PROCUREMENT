import { cn } from '@/lib/cn';

export interface SkeletonProps {
  className?: string;
  'aria-label'?: string;
}

export function Skeleton({
  className,
  'aria-label': ariaLabel = 'Loading',
}: SkeletonProps): JSX.Element {
  return (
    <div
      role="status"
      aria-label={ariaLabel}
      aria-busy="true"
      className={cn(
        'animate-pulse rounded-md bg-slate-200/70 dark:bg-slate-800',
        className,
      )}
    />
  );
}

export function SkeletonText({ lines = 3 }: { lines?: number }): JSX.Element {
  return (
    <div className="space-y-2" role="status" aria-label="Loading content">
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton
          key={i}
          className={cn('h-3', i === lines - 1 ? 'w-2/3' : 'w-full')}
        />
      ))}
    </div>
  );
}

export interface SkeletonTableProps {
  rows?: number;
  columns?: number;
}

export function SkeletonTable({
  rows = 6,
  columns = 5,
}: SkeletonTableProps): JSX.Element {
  return (
    <div
      className="divide-y divide-slate-200 dark:divide-slate-800"
      role="status"
      aria-label="Loading table"
      aria-busy="true"
    >
      {Array.from({ length: rows }, (_, r) => (
        <div key={r} className="grid gap-3 px-5 py-3" style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}>
          {Array.from({ length: columns }, (__, c) => (
            <Skeleton key={c} className="h-3 w-full" aria-label="" />
          ))}
        </div>
      ))}
    </div>
  );
}
