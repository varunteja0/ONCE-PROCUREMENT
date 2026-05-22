/**
 * Re-exports for the shared UI design system.
 *
 * Import surface:
 *   import { Button, Input, Card, Skeleton, EmptyState } from '@/components/ui';
 */
export { Button, type ButtonProps } from './Button';
export { Input, type InputProps } from './Input';
export { Select, type SelectProps, type SelectOption } from './Select';
export { Textarea, type TextareaProps } from './Textarea';
export { Card, CardHeader, type CardProps, type CardHeaderProps } from './Card';
export {
  Skeleton,
  SkeletonText,
  SkeletonTable,
  type SkeletonProps,
  type SkeletonTableProps,
} from './Skeleton';
export { EmptyState, type EmptyStateProps, type EmptyStateAction } from './EmptyState';
export { ErrorState, type ErrorStateProps } from './ErrorState';
export { StatusBadge, type StatusBadgeProps } from './StatusBadge';
export { DateDisplay, type DateDisplayProps } from './DateDisplay';
export { MoneyDisplay, type MoneyDisplayProps } from './MoneyDisplay';
export {
  PaginationControls,
  type PaginationControlsProps,
} from './PaginationControls';
export { SearchInput, type SearchInputProps } from './SearchInput';
export { Modal, type ModalProps } from './Modal';
export { MultiSelect, type MultiSelectOption, type MultiSelectProps } from './MultiSelect';
export { Tooltip, type TooltipProps } from './Tooltip';
