import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

export interface TooltipProps {
  label: string;
  children: ReactNode;
  className?: string;
}

/**
 * CSS-only tooltip — no JS positioning. Trigger element must accept
 * `aria-label` semantics; the tooltip is decorative reinforcement.
 */
export function Tooltip({ label, children, className }: TooltipProps): JSX.Element {
  return (
    <span className={cn('group/tooltip relative inline-flex', className)}>
      {children}
      <span
        role="tooltip"
        className="pointer-events-none absolute left-1/2 top-full z-50 mt-1 -translate-x-1/2 whitespace-nowrap rounded bg-slate-900 px-2 py-1 text-xs text-white opacity-0 shadow-lg transition group-hover/tooltip:opacity-100 group-focus-within/tooltip:opacity-100 dark:bg-slate-100 dark:text-slate-900"
      >
        {label}
      </span>
    </span>
  );
}
