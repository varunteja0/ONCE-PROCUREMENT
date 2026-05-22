import { forwardRef, useId, type InputHTMLAttributes } from 'react';
import { cn } from '@/lib/cn';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string;
  containerClassName?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  (
    {
      id,
      label,
      hint,
      error,
      containerClassName,
      className,
      required,
      ...rest
    },
    ref,
  ) => {
    const generatedId = useId();
    const inputId = id ?? generatedId;
    const hintId = `${inputId}-hint`;
    const errorId = `${inputId}-error`;
    const describedBy = error ? errorId : hint ? hintId : undefined;
    return (
      <div className={cn('space-y-1', containerClassName)}>
        {label ? (
          <label
            htmlFor={inputId}
            className="block text-xs font-medium text-slate-700 dark:text-slate-200"
          >
            {label}
            {required ? <span className="ml-0.5 text-rose-600">*</span> : null}
          </label>
        ) : null}
        <input
          ref={ref}
          id={inputId}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          required={required}
          className={cn(
            'block w-full rounded-md border bg-white px-3 py-1.5 text-sm shadow-sm transition focus:outline-none focus:ring-2 focus:ring-slate-900 dark:bg-slate-900 dark:text-slate-100',
            error
              ? 'border-rose-400 focus:ring-rose-500'
              : 'border-slate-300 dark:border-slate-700',
            'disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500 dark:disabled:bg-slate-800',
            className,
          )}
          {...rest}
        />
        {error ? (
          <p
            id={errorId}
            className="text-xs text-rose-600 dark:text-rose-400"
            role="alert"
          >
            {error}
          </p>
        ) : hint ? (
          <p
            id={hintId}
            className="text-xs text-slate-500 dark:text-slate-400"
          >
            {hint}
          </p>
        ) : null}
      </div>
    );
  },
);
Input.displayName = 'Input';
