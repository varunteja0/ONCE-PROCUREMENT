import type { ReactNode } from 'react';
import { AlertTriangle, RotateCw } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { extractErrorMessage } from '@/services/api';

export interface ErrorStateProps {
  title?: string;
  error?: unknown;
  description?: ReactNode;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({
  title = 'Something went wrong',
  error,
  description,
  onRetry,
  className,
}: ErrorStateProps): JSX.Element {
  const msg =
    description ??
    (error !== undefined
      ? extractErrorMessage(error, 'Please try again.')
      : 'Please try again.');

  return (
    <div
      role="alert"
      aria-live="assertive"
      className={[
        'flex flex-col items-center justify-center rounded-lg border border-rose-200 bg-rose-50 px-6 py-10 text-center dark:border-rose-900/40 dark:bg-rose-950/30',
        className ?? '',
      ]
        .filter(Boolean)
        .join(' ')}
    >
      <div
        aria-hidden="true"
        className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-full bg-rose-100 text-rose-700 dark:bg-rose-900/50 dark:text-rose-300"
      >
        <AlertTriangle className="h-5 w-5" />
      </div>
      <h3 className="text-sm font-semibold text-rose-900 dark:text-rose-200">
        {title}
      </h3>
      <p className="mt-1 max-w-md text-xs text-rose-800 dark:text-rose-300">
        {msg}
      </p>
      {onRetry ? (
        <Button
          variant="outline"
          size="sm"
          onClick={onRetry}
          leadingIcon={<RotateCw className="h-3.5 w-3.5" />}
          className="mt-4"
        >
          Retry
        </Button>
      ) : null}
    </div>
  );
}
