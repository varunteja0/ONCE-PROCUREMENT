import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { FileCheck2 } from 'lucide-react';
import { ResourcePage } from '@/components/ResourcePage';
import { SupplierPicker } from '@/components/SupplierPicker';
import { Button, Input, Textarea, DateDisplay, MoneyDisplay } from '@/components/ui';
import { coisHooks } from '@/hooks/useArtifacts';
import { coiSchema, type CoiFormValues } from '@/schemas/artifacts';
import type { Coi, CoiCreateInput } from '@/types/api';

function CoiForm({
  onSubmit,
  submitting,
  onCancel,
}: {
  onSubmit: (input: CoiCreateInput) => Promise<void>;
  submitting: boolean;
  onCancel: () => void;
}): JSX.Element {
  const form = useForm<CoiFormValues>({
    resolver: zodResolver(coiSchema),
    defaultValues: {
      supplier_id: '',
      carrier: '',
      policy_number: '',
      effective_date: '',
      expires_at: '',
      coverage_type: '',
      limit_amount: '',
      file_url: '',
      notes: '',
    },
  });

  return (
    <form
      onSubmit={form.handleSubmit((v) => onSubmit(v as unknown as CoiCreateInput))}
      className="space-y-3"
      noValidate
    >
      <SupplierPicker
        label="Supplier"
        required
        {...form.register('supplier_id')}
        error={form.formState.errors.supplier_id?.message}
      />
      <Input
        label="Carrier"
        required
        {...form.register('carrier')}
        error={form.formState.errors.carrier?.message}
      />
      <div className="grid grid-cols-2 gap-3">
        <Input label="Policy number" {...form.register('policy_number')} />
        <Input
          label="Coverage type"
          {...form.register('coverage_type')}
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Input
          label="Effective date"
          type="date"
          {...form.register('effective_date')}
        />
        <Input
          label="Expires at"
          type="date"
          required
          {...form.register('expires_at')}
          error={form.formState.errors.expires_at?.message}
        />
      </div>
      <Input
        label="Limit amount (USD)"
        inputMode="decimal"
        {...form.register('limit_amount')}
      />
      <Input label="File URL" type="url" {...form.register('file_url')} />
      <Textarea label="Notes" rows={2} {...form.register('notes')} />
      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" loading={submitting}>
          Create COI
        </Button>
      </div>
    </form>
  );
}

export default function Cois(): JSX.Element {
  return (
    <ResourcePage<Coi, CoiCreateInput>
      title="Certificates of Insurance"
      description="Track COI policy expirations across all suppliers."
      pluralNoun="COIs"
      singularNoun="COI"
      emptyIcon={FileCheck2}
      rowKey={(r) => r.id}
      columns={[
        {
          key: 'supplier',
          header: 'Supplier',
          cell: (r) => (
            <span className="font-mono text-xs">{r.supplier_id.slice(0, 8)}</span>
          ),
        },
        { key: 'carrier', header: 'Carrier', cell: (r) => r.carrier },
        {
          key: 'policy',
          header: 'Policy #',
          cell: (r) => r.policy_number ?? '—',
        },
        {
          key: 'limit',
          header: 'Limit',
          align: 'right',
          cell: (r) => <MoneyDisplay value={r.limit_amount} />,
        },
        {
          key: 'expires',
          header: 'Expires',
          cell: (r) => <DateDisplay value={r.expires_at} />,
        },
      ]}
      useList={coisHooks.useList}
      useCreate={coisHooks.useCreate}
      renderForm={(args) => <CoiForm {...args} />}
    />
  );
}
