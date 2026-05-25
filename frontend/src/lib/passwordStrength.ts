/**
 * Lightweight password strength heuristic for client-side hints.
 * Server is still the source of truth.
 */

export type StrengthScore = 0 | 1 | 2 | 3 | 4;

export interface StrengthResult {
  score: StrengthScore;
  label: string;
  reasons: string[];
}

const LABELS: Readonly<Record<StrengthScore, string>> = {
  0: 'Weak',
  1: 'Fair',
  2: 'Good',
  3: 'Strong',
  4: 'Excellent',
};

const COMMON_PATTERNS = [
  'password',
  '12345',
  'qwerty',
] as const;

function clamp(n: number): StrengthScore {
  if (n <= 0) return 0;
  if (n >= 4) return 4;
  return n as StrengthScore;
}

export function scorePassword(
  pw: string,
  hints?: { email?: string | null },
): StrengthResult {
  const reasons: string[] = [];
  if (typeof pw !== 'string' || pw.length === 0) {
    return { score: 0, label: LABELS[0], reasons: ['Enter a password.'] };
  }

  let raw = 0;
  if (pw.length >= 12) {
    raw += 1;
  } else {
    reasons.push('Use at least 12 characters.');
  }
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) {
    raw += 1;
  } else {
    reasons.push('Mix uppercase and lowercase letters.');
  }
  if (/[0-9]/.test(pw)) {
    raw += 1;
  } else {
    reasons.push('Add a number.');
  }
  if (/[^A-Za-z0-9]/.test(pw)) {
    raw += 1;
  } else {
    reasons.push('Add a symbol.');
  }

  const lower = pw.toLowerCase();
  const emailLocal = (hints?.email ?? '').split('@')[0]?.toLowerCase() ?? '';
  if (emailLocal.length >= 3 && (lower === emailLocal || lower.includes(emailLocal))) {
    raw -= 1;
    reasons.push('Do not reuse your email username.');
  }
  if (COMMON_PATTERNS.some((p) => lower.includes(p))) {
    raw -= 1;
    reasons.push('Avoid common patterns like "password", "12345", or "qwerty".');
  }

  const score = clamp(raw);
  return { score, label: LABELS[score], reasons };
}
