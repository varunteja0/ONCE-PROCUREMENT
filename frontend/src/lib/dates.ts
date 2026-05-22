import { format, formatDistanceToNowStrict, isValid, parseISO } from 'date-fns';

export function parseIso(value: string | null | undefined): Date | null {
  if (!value) return null;
  const d = parseISO(value);
  return isValid(d) ? d : null;
}

export function formatDateTime(
  value: string | null | undefined,
  fallback = '—',
): string {
  const d = parseIso(value);
  if (!d) return fallback;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(d);
}

export function formatDate(
  value: string | null | undefined,
  fallback = '—',
): string {
  const d = parseIso(value);
  if (!d) return fallback;
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(d);
}

export function formatPattern(
  value: string | null | undefined,
  pattern: string,
  fallback = '—',
): string {
  const d = parseIso(value);
  if (!d) return fallback;
  return format(d, pattern);
}

export function fromNow(value: string | null | undefined, fallback = '—'): string {
  const d = parseIso(value);
  if (!d) return fallback;
  return `${formatDistanceToNowStrict(d)} ago`;
}

export function isWithinNextDays(
  value: string | null | undefined,
  days: number,
): boolean {
  const d = parseIso(value);
  if (!d) return false;
  const ms = d.getTime() - Date.now();
  return ms >= 0 && ms <= days * 86_400_000;
}

export function isWithinPastDays(
  value: string | null | undefined,
  days: number,
): boolean {
  const d = parseIso(value);
  if (!d) return false;
  const ms = Date.now() - d.getTime();
  return ms >= 0 && ms <= days * 86_400_000;
}
