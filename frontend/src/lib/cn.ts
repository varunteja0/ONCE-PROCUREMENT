import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * `cn` — merge Tailwind class lists with conflict resolution.
 * Combines `clsx` (conditional composition) with `tailwind-merge`
 * (last-write-wins for conflicting utilities, e.g. `p-2 p-4` → `p-4`).
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
