import { useEffect, useRef, type ReactNode } from 'react';
import { X } from 'lucide-react';
import { cn } from '@/lib/cn';
import { Button } from '@/components/ui/Button';

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  closeOnBackdrop?: boolean;
}

const SIZE_CLASS: Record<NonNullable<ModalProps['size']>, string> = {
  sm: 'max-w-sm',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
  xl: 'max-w-4xl',
};

/**
 * Accessible modal dialog. Uses native <dialog> semantics via role+aria.
 * Traps focus on first focusable element, closes on Escape, restores focus
 * on unmount.
 */
export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = 'md',
  closeOnBackdrop = true,
}: ModalProps): JSX.Element | null {
  const ref = useRef<HTMLDivElement>(null);
  const previouslyFocused = useRef<Element | null>(null);

  useEffect(() => {
    if (!open) return undefined;
    previouslyFocused.current = document.activeElement;

    const firstFocusable = ref.current?.querySelector<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    firstFocusable?.focus();

    function onKey(e: KeyboardEvent): void {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
      }
    }
    window.addEventListener('keydown', onKey);
    const original = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = original;
      if (previouslyFocused.current instanceof HTMLElement) {
        previouslyFocused.current.focus();
      }
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-slate-900/40 px-4 py-8"
      role="presentation"
      onMouseDown={(e) => {
        if (closeOnBackdrop && e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        aria-describedby={description ? 'modal-desc' : undefined}
        className={cn(
          'w-full overflow-hidden rounded-lg bg-white shadow-xl dark:bg-slate-900',
          SIZE_CLASS[size],
        )}
      >
        <header className="flex items-start justify-between border-b border-slate-200 px-5 py-3 dark:border-slate-800">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              {title}
            </h2>
            {description ? (
              <p id="modal-desc" className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                {description}
              </p>
            ) : null}
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            aria-label="Close dialog"
            className="-mr-1"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </Button>
        </header>
        <div className="max-h-[70vh] overflow-y-auto px-5 py-4">{children}</div>
        {footer ? (
          <footer className="flex justify-end gap-2 border-t border-slate-200 bg-slate-50 px-5 py-3 dark:border-slate-800 dark:bg-slate-950/30">
            {footer}
          </footer>
        ) : null}
      </div>
    </div>
  );
}
