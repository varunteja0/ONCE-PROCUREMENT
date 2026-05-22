import { useMemo } from 'react';
import { useSuppliers } from '@/hooks/useSuppliers';
import { Select, type SelectProps } from '@/components/ui/Select';

export interface SupplierPickerProps
  extends Omit<SelectProps, 'options' | 'placeholder'> {
  placeholder?: string;
}

/**
 * Async-loaded supplier select. Calls `/v1/suppliers` (up to 200 rows) and
 * presents them sorted by legal name.
 */
export function SupplierPicker(props: SupplierPickerProps): JSX.Element {
  const query = useSuppliers({ pageSize: 200 });
  const options = useMemo(
    () =>
      (query.data ?? [])
        .map((s) => ({ value: s.id, label: s.legal_name }))
        .sort((a, b) => a.label.localeCompare(b.label)),
    [query.data],
  );

  return (
    <Select
      {...props}
      options={options}
      placeholder={
        query.isLoading
          ? 'Loading suppliers…'
          : props.placeholder ?? 'Select a supplier'
      }
      disabled={props.disabled || query.isLoading}
    />
  );
}
