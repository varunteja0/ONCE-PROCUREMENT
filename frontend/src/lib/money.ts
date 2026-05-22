export function formatMoney(
  value: number | string | null | undefined,
  currency: string = 'USD',
  fallback = '—',
): string {
  if (value === null || value === undefined || value === '') return fallback;
  const n = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(n)) return fallback;
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency,
    maximumFractionDigits: 2,
  }).format(n);
}
