// One-line shim — `@/components/StatusPill` is the legacy path.
// New code SHOULD import `StatusBadge` from `@/components/ui`.
// Default export preserved so existing `import StatusPill from ...` works.
export { StatusBadge as default, StatusBadge } from '@/components/ui/StatusBadge';
export type { StatusBadgeProps as StatusPillProps } from '@/components/ui/StatusBadge';
