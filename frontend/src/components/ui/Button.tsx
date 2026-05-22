import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/cn';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'outline';
type Size = 'sm' | 'md' | 'lg';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  leadingIcon?: React.ReactNode;
  trailingIcon?: React.ReactNode;
  fullWidth?: boolean;
}

const VARIANT_CLASS: Record<Variant, string> = {
  primary:
    'bg-slate-900 text-white hover:bg-slate-800 focus-visible:ring-slate-900 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white',
  secondary:
    'bg-slate-100 text-slate-900 hover:bg-slate-200 focus-visible:ring-slate-400 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700',
  outline:
    'border border-slate-300 bg-white text-slate-700 hover:bg-slate-100 focus-visible:ring-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800',
  ghost:
    'text-slate-700 hover:bg-slate-100 focus-visible:ring-slate-400 dark:text-slate-200 dark:hover:bg-slate-800',
  danger:
    'bg-rose-600 text-white hover:bg-rose-500 focus-visible:ring-rose-600',
};

const SIZE_CLASS: Record<Size, string> = {
  sm: 'h-8 px-2.5 text-xs gap-1.5',
  md: 'h-9 px-3 text-sm gap-2',
  lg: 'h-10 px-4 text-sm gap-2',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'primary',
      size = 'md',
      loading = false,
      leadingIcon,
      trailingIcon,
      fullWidth = false,
      className,
      children,
      disabled,
      type = 'button',
      ...rest
    },
    ref,
  ) => {
    const isDisabled = disabled || loading;
    return (
      <button
        ref={ref}
        type={type}
        disabled={isDisabled}
        aria-busy={loading || undefined}
        className={cn(
          'inline-flex select-none items-center justify-center rounded-md font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60',
          VARIANT_CLASS[variant],
          SIZE_CLASS[size],
          fullWidth && 'w-full',
          className,
        )}
        {...rest}
      >
        {loading ? (
          <Loader2 className="h-4 w-4 shrink-0 animate-spin" aria-hidden="true" />
        ) : leadingIcon ? (
          <span className="shrink-0" aria-hidden="true">
            {leadingIcon}
          </span>
        ) : null}
        {children}
        {trailingIcon && !loading ? (
          <span className="shrink-0" aria-hidden="true">
            {trailingIcon}
          </span>
        ) : null}
      </button>
    );
  },
);
Button.displayName = 'Button';
