import { forwardRef, useId, type SelectHTMLAttributes } from 'react';
import { cn } from '@/lib/cn';

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectProps
  extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'children'> {
  label?: string;
  hint?: string;
  error?: string;
  options: ReadonlyArray<SelectOption>;
  containerClassName?: string;
  placeholder?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  (
    {
      id,
      label,
      hint,
      error,
      options,
      placeholder,
      containerClassName,
      className,
      required,
      ...rest
    },
    ref,
  ) => {
    const generatedId = useId();
    const selectId = id ?? generatedId;
    const hintId = `${selectId}-hint`;
    const errorId = `${selectId}-error`;
    const describedBy = error ? errorId : hint ? hintId : undefined;
    return (
      <div className={cn('space-y-1', containerClassName)}>
        {label ? (
          <label
            htmlFor={selectId}
            className="block text-xs font-medium text-slate-700 dark:text-slate-200"
          >
            {label}
            {required ? <span className="ml-0.5 text-rose-600">*</span> : null}
          </label>
        ) : null}
        <select
          ref={ref}
          id={selectId}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          required={required}
          className={cn(
            'block w-full rounded-md border bg-white px-3 py-1.5 text-sm shadow-sm transition focus:outline-none focus:ring-2 focus:ring-slate-900 dark:bg-slate-900 dark:text-slate-100',
            error
              ? 'border-rose-400 focus:ring-rose-500'
              : 'border-slate-300 dark:border-slate-700',
            className,
          )}
          {...rest}
        >
          {placeholder ? (
            <option value="" disabled>
              {placeholder}
            </option>
          ) : null}
          {options.map((o) => (
            <option key={o.value} value={o.value} disabled={o.disabled}>
              {o.label}
            </option>
          ))}
        </select>
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
Select.displayName = 'Select';
