import { formatDateTime, formatDate, fromNow } from '@/lib/dates';

export interface DateDisplayProps {
  value: string | null | undefined;
  mode?: 'datetime' | 'date' | 'relative';
  fallback?: string;
  className?: string;
}

export function DateDisplay({
  value,
  mode = 'datetime',
  fallback = '—',
  className,
}: DateDisplayProps): JSX.Element {
  let text: string;
  switch (mode) {
    case 'date':
      text = formatDate(value, fallback);
      break;
    case 'relative':
      text = fromNow(value, fallback);
      break;
    case 'datetime':
    default:
      text = formatDateTime(value, fallback);
      break;
  }
  return (
    <time
      className={className}
      dateTime={value ?? undefined}
      title={value ? formatDateTime(value) : undefined}
    >
      {text}
    </time>
  );
}
