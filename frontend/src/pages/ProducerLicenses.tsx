import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { BadgeCheck } from 'lucide-react';
import { ResourcePage } from '@/components/ResourcePage';
import { SupplierPicker } from '@/components/SupplierPicker';
import { Button, Input, Textarea, DateDisplay } from '@/components/ui';
import { producerLicensesHooks } from '@/hooks/useArtifacts';
import {
  producerLicenseSchema,
  type ProducerLicenseFormValues,
} from '@/schemas/artifacts';
import type { ProducerLicense, ProducerLicenseCreateInput } from '@/types/api';

function toCreateInput(v: ProducerLicenseFormValues): ProducerLicenseCreateInput {
  return {
    supplier_id: v.supplier_id,
    state: v.state,
    license_number: v.license_number,
    license_type: v.license_type ?? null,
    expires_at: v.expires_at,
    file_url: v.file_url ?? null,
    notes: v.notes ?? null,
  };
}

function LicenseForm({
  onSubmit,
  submitting,
  onCancel,
}: {
  onSubmit: (input: ProducerLicenseCreateInput) => Promise<void>;
  submitting: boolean;
  onCancel: () => void;
}): JSX.Element {
  const form = useForm<ProducerLicenseFormValues>({
    resolver: zodResolver(producerLicenseSchema),
    defaultValues: {
      supplier_id: '',
      state: '',
      license_number: '',
      license_type: '',
      expires_at: '',
      file_url: '',
      notes: '',
    },
  });

  return (
    <form
      onSubmit={form.handleSubmit((v) => onSubmit(toCreateInput(v)))}
      className="space-y-3"
      noValidate
    >
      <SupplierPicker
        label="Supplier"
        required
        {...form.register('supplier_id')}
        error={form.formState.errors.supplier_id?.message}
      />
      <div className="grid grid-cols-2 gap-3">
        <Input
          label="State (2-letter)"
          required
          maxLength={2}
          {...form.register('state')}
          error={form.formState.errors.state?.message}
        />
        <Input
          label="License number"
          required
          {...form.register('license_number')}
          error={form.formState.errors.license_number?.message}
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Input label="License type" {...form.register('license_type')} />
        <Input
          label="Expires at"
          type="date"
          required
          {...form.register('expires_at')}
          error={form.formState.errors.expires_at?.message}
        />
      </div>
      <Input label="File URL" type="url" {...form.register('file_url')} />
      <Textarea label="Notes" rows={2} {...form.register('notes')} />
      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" loading={submitting}>
          Create license
        </Button>
      </div>
    </form>
  );
}

export default function ProducerLicenses(): JSX.Element {
  return (
    <ResourcePage<ProducerLicense, ProducerLicenseCreateInput>
      title="Producer licenses"
      description="State licensing records for producing agents."
      pluralNoun="producer licenses"
      singularNoun="producer license"
      emptyIcon={BadgeCheck}
      rowKey={(r) => r.id}
      columns={[
        {
          key: 'supplier',
          header: 'Supplier',
          cell: (r) => (
            <span className="font-mono text-xs">{r.supplier_id.slice(0, 8)}</span>
          ),
        },
        { key: 'state', header: 'State', cell: (r) => r.state },
        {
          key: 'license',
          header: 'License #',
          cell: (r) => <span className="font-mono text-xs">{r.license_number}</span>,
        },
        {
          key: 'type',
          header: 'Type',
          cell: (r) => r.license_type ?? '—',
        },
        {
          key: 'expires',
          header: 'Expires',
          cell: (r) => <DateDisplay value={r.expires_at} />,
        },
      ]}
      useList={producerLicensesHooks.useList}
      useCreate={producerLicensesHooks.useCreate}
      renderForm={(args) => <LicenseForm {...args} />}
    />
  );
}
