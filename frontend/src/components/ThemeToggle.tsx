import { useEffect, useState } from 'react';
import { Monitor, Moon, Sun } from 'lucide-react';
import { applyTheme, readTheme, writeTheme, type Theme } from '@/lib/theme';
import { cn } from '@/lib/cn';

const OPTIONS: ReadonlyArray<{ value: Theme; label: string; icon: typeof Sun }> = [
  { value: 'light', label: 'Light theme', icon: Sun },
  { value: 'dark', label: 'Dark theme', icon: Moon },
  { value: 'system', label: 'System theme', icon: Monitor },
];

export function ThemeToggle(): JSX.Element {
  const [theme, setTheme] = useState<Theme>(() => readTheme());

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  useEffect(() => {
    if (theme !== 'system') return undefined;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = (): void => applyTheme('system');
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, [theme]);

  return (
    <div
      role="radiogroup"
      aria-label="Theme"
      className="inline-flex items-center rounded-md border border-slate-200 bg-white p-0.5 dark:border-slate-700 dark:bg-slate-900"
    >
      {OPTIONS.map(({ value, label, icon: Icon }) => {
        const active = theme === value;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={label}
            onClick={() => {
              setTheme(value);
              writeTheme(value);
            }}
            className={cn(
              'inline-flex h-6 w-6 items-center justify-center rounded transition',
              active
                ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                : 'text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800',
            )}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        );
      })}
    </div>
  );
}
