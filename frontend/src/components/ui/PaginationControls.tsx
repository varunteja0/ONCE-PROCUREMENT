import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/cn';

export interface PaginationControlsProps {
  page: number;
  pageSize: number;
  total: number | null;
  onPageChange: (page: number) => void;
  className?: string;
  isLoading?: boolean;
}

export function PaginationControls({
  page,
  pageSize,
  total,
  onPageChange,
  className,
  isLoading = false,
}: PaginationControlsProps): JSX.Element {
  const totalPages =
    total !== null && total >= 0 ? Math.max(1, Math.ceil(total / pageSize)) : null;
  const start = (page - 1) * pageSize + 1;
  const end = total !== null ? Math.min(total, page * pageSize) : null;
  const canPrev = page > 1 && !isLoading;
  const canNext =
    !isLoading && (totalPages === null ? true : page < totalPages);

  return (
    <nav
      aria-label="Pagination"
      className={cn(
        'flex items-center justify-between border-t border-slate-200 px-5 py-2 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400',
        className,
      )}
    >
      <p>
        {total === 0 ? (
          'No results'
        ) : total !== null ? (
          <>
            Showing <span className="font-medium text-slate-700 dark:text-slate-200">{start.toLocaleString()}</span>
            –<span className="font-medium text-slate-700 dark:text-slate-200">{end?.toLocaleString()}</span>
            {' '}of{' '}
            <span className="font-medium text-slate-700 dark:text-slate-200">{total.toLocaleString()}</span>
          </>
        ) : (
          <>Page {page}</>
        )}
      </p>
      <div className="flex items-center gap-1">
        <Button
          variant="outline"
          size="sm"
          disabled={!canPrev}
          onClick={() => onPageChange(Math.max(1, page - 1))}
          aria-label="Previous page"
          leadingIcon={<ChevronLeft className="h-3.5 w-3.5" />}
        >
          Prev
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={!canNext}
          onClick={() => onPageChange(page + 1)}
          aria-label="Next page"
          trailingIcon={<ChevronRight className="h-3.5 w-3.5" />}
        >
          Next
        </Button>
      </div>
    </nav>
  );
}
