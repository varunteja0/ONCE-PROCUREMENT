import { useId, type ChangeEvent } from 'react';
import { Search, X } from 'lucide-react';
import { cn } from '@/lib/cn';

export interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  label?: string;
  className?: string;
  ariaLabel?: string;
}

export function SearchInput({
  value,
  onChange,
  placeholder = 'Search…',
  label,
  className,
  ariaLabel,
}: SearchInputProps): JSX.Element {
  const id = useId();
  function onInput(e: ChangeEvent<HTMLInputElement>): void {
    onChange(e.target.value);
  }
  return (
    <div className={cn('relative', className)}>
      {label ? (
        <label htmlFor={id} className="sr-only">
          {label}
        </label>
      ) : null}
      <Search
        aria-hidden="true"
        className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
      />
      <input
        id={id}
        type="search"
        value={value}
        onChange={onInput}
        placeholder={placeholder}
        aria-label={ariaLabel ?? label ?? placeholder}
        className="block w-full rounded-md border border-slate-300 bg-white py-1.5 pl-8 pr-8 text-sm shadow-sm transition focus:outline-none focus:ring-2 focus:ring-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
      />
      {value ? (
        <button
          type="button"
          onClick={() => onChange('')}
          aria-label="Clear search"
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800"
        >
          <X className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      ) : null}
    </div>
  );
}
