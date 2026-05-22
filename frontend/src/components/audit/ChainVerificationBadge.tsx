// --- L3.10 audit ---
import { useChainVerification } from '@/hooks/useAudit';

export interface ChainVerificationBadgeProps {
  refetchInterval?: number | false;
  className?: string;
}

export function ChainVerificationBadge({
  refetchInterval = 60_000,
  className,
}: ChainVerificationBadgeProps) {
  const { data, isLoading, isError } = useChainVerification({ refetchInterval });

  let label = 'Verifying…';
  let tone: 'pending' | 'ok' | 'bad' = 'pending';
  if (!isLoading && !isError && data) {
    if (data.valid) {
      label = `Chain verified · ${data.rows_checked}`;
      tone = 'ok';
    } else {
      label = `Chain tampered · ${data.breaks.length} break${data.breaks.length === 1 ? '' : 's'}`;
      tone = 'bad';
    }
  } else if (isError) {
    label = 'Chain check failed';
    tone = 'bad';
  }

  const toneClass =
    tone === 'ok'
      ? 'bg-green-100 text-green-800 border-green-300'
      : tone === 'bad'
        ? 'bg-red-100 text-red-800 border-red-300'
        : 'bg-gray-100 text-gray-700 border-gray-300';

  return (
    <span
      data-testid="chain-verification-badge"
      data-tone={tone}
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${toneClass} ${className ?? ''}`}
      title={
        data
          ? `Last verified · ${data.rows_checked} rows`
          : 'Chain verification status'
      }
    >
      {tone === 'ok' && <span aria-hidden>✓</span>}
      {tone === 'bad' && <span aria-hidden>✗</span>}
      {label}
    </span>
  );
}

export default ChainVerificationBadge;
