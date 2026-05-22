export type Theme = 'light' | 'dark' | 'system';

const STORAGE_KEY = 'once.theme';

function prefersDark(): boolean {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

export function readTheme(): Theme {
  if (typeof window === 'undefined') return 'system';
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw === 'light' || raw === 'dark' || raw === 'system') return raw;
  } catch {
    /* ignore */
  }
  return 'system';
}

export function applyTheme(theme: Theme): void {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  const isDark = theme === 'dark' || (theme === 'system' && prefersDark());
  root.classList.toggle('dark', isDark);
  root.style.colorScheme = isDark ? 'dark' : 'light';
}

export function writeTheme(theme: Theme): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    /* ignore */
  }
  applyTheme(theme);
}
