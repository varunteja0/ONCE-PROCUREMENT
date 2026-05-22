import { cn } from '@/lib/cn';
import { Check } from 'lucide-react';
import { useId, type ReactNode } from 'react';

export interface MultiSelectOption<T extends string> {
  value: T;
  label: string;
  description?: ReactNode;
  disabled?: boolean;
}

export interface MultiSelectProps<T extends string> {
  options: ReadonlyArray<MultiSelectOption<T>>;
  value: ReadonlyArray<T>;
  onChange: (value: T[]) => void;
  label?: string;
  hint?: string;
  error?: string;
  className?: string;
}

/**
 * Keyboard-accessible multi-select rendered as a list of checkboxes.
 * Each option is independently toggle-able with Space/Enter.
 */
export function MultiSelect<T extends string>({
  options,
  value,
  onChange,
  label,
  hint,
  error,
  className,
}: MultiSelectProps<T>): JSX.Element {
  const id = useId();
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;
  const selected = new Set(value);

  function toggle(v: T): void {
    const next = new Set(selected);
    if (next.has(v)) {
      next.delete(v);
    } else {
      next.add(v);
    }
    onChange(Array.from(next));
  }

  return (
    <fieldset
      className={cn('space-y-1', className)}
      aria-describedby={error ? errorId : hint ? hintId : undefined}
      aria-invalid={error ? true : undefined}
    >
      {label ? (
        <legend className="text-xs font-medium text-slate-700 dark:text-slate-200">
          {label}
        </legend>
      ) : null}
      <ul className="grid gap-1 sm:grid-cols-2">
        {options.map((opt) => {
          const checked = selected.has(opt.value);
          return (
            <li key={opt.value}>
              <label
                className={cn(
                  'flex cursor-pointer items-start gap-2 rounded-md border p-2 transition',
                  checked
                    ? 'border-slate-900 bg-slate-50 dark:border-slate-100 dark:bg-slate-800'
                    : 'border-slate-200 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800',
                  opt.disabled && 'cursor-not-allowed opacity-60',
                )}
              >
                <input
                  type="checkbox"
                  className="sr-only"
                  checked={checked}
                  disabled={opt.disabled}
                  onChange={() => toggle(opt.value)}
                />
                <span
                  aria-hidden="true"
                  className={cn(
                    'mt-0.5 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded border',
                    checked
                      ? 'border-slate-900 bg-slate-900 text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-900'
                      : 'border-slate-300 bg-white dark:border-slate-600 dark:bg-slate-900',
                  )}
                >
                  {checked ? <Check className="h-3 w-3" /> : null}
                </span>
                <span className="min-w-0">
                  <span className="block text-sm font-medium text-slate-900 dark:text-slate-100">
                    {opt.label}
                  </span>
                  {opt.description ? (
                    <span className="block text-xs text-slate-500 dark:text-slate-400">
                      {opt.description}
                    </span>
                  ) : null}
                </span>
              </label>
            </li>
          );
        })}
      </ul>
      {error ? (
        <p id={errorId} role="alert" className="text-xs text-rose-600 dark:text-rose-400">
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="text-xs text-slate-500 dark:text-slate-400">
          {hint}
        </p>
      ) : null}
    </fieldset>
  );
}
