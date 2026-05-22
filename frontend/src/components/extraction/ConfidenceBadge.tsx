// --- L3.8 pdf extraction ---
import clsx from 'clsx';

export type ConfidenceTier = 'green' | 'yellow' | 'red';

export interface ConfidenceBadgeProps {
  /** Score in the closed interval [0, 1]; clamped if outside. */
  value: number;
  className?: string;
  /** Optional override label, e.g. "auto" or "n/a". */
  label?: string;
}

export const GREEN_THRESHOLD = 0.9;
export const YELLOW_THRESHOLD = 0.6;

export function tierFor(value: number): ConfidenceTier {
  if (value >= GREEN_THRESHOLD) return 'green';
  if (value >= YELLOW_THRESHOLD) return 'yellow';
  return 'red';
}

const TIER_CLASSES: Record<ConfidenceTier, string> = {
  green: 'bg-green-100 text-green-800 ring-1 ring-green-200',
  yellow: 'bg-yellow-100 text-yellow-800 ring-1 ring-yellow-200',
  red: 'bg-red-100 text-red-800 ring-1 ring-red-200',
};

export function ConfidenceBadge({
  value,
  className,
  label,
}: ConfidenceBadgeProps): JSX.Element {
  const clamped = Math.max(0, Math.min(1, Number.isFinite(value) ? value : 0));
  const tier = tierFor(clamped);
  const pct = Math.round(clamped * 100);
  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold',
        TIER_CLASSES[tier],
        className,
      )}
      role="status"
      aria-label={`confidence ${pct} percent (${tier})`}
      data-testid="confidence-badge"
      data-tier={tier}
    >
      {label ?? `${pct}%`}
    </span>
  );
}

export default ConfidenceBadge;
// --- /L3.8 pdf extraction ---
