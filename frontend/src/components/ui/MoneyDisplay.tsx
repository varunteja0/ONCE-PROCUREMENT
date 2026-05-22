import { formatMoney } from '@/lib/money';

export interface MoneyDisplayProps {
  value: number | string | null | undefined;
  currency?: string;
  fallback?: string;
  className?: string;
}

export function MoneyDisplay({
  value,
  currency = 'USD',
  fallback = '—',
  className,
}: MoneyDisplayProps): JSX.Element {
  return (
    <span className={className} data-currency={currency}>
      {formatMoney(value, currency, fallback)}
    </span>
  );
}
