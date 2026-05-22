import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { ShieldCheck } from 'lucide-react';
import { ResourcePage } from '@/components/ResourcePage';
import { SupplierPicker } from '@/components/SupplierPicker';
import { Button, Input, Textarea, DateDisplay, MoneyDisplay } from '@/components/ui';
import { eoCertificatesHooks } from '@/hooks/useArtifacts';
import {
  eoCertificateSchema,
  type EoCertificateFormValues,
} from '@/schemas/artifacts';
import type { EoCertificate, EoCertificateCreateInput } from '@/types/api';

function EoForm({
  onSubmit,
  submitting,
  onCancel,
}: {
  onSubmit: (input: EoCertificateCreateInput) => Promise<void>;
  submitting: boolean;
  onCancel: () => void;
}): JSX.Element {
  const form = useForm<EoCertificateFormValues>({
    resolver: zodResolver(eoCertificateSchema),
    defaultValues: {
      supplier_id: '',
      carrier: '',
      policy_number: '',
      limit_amount: '',
      retroactive_date: '',
      expires_at: '',
      file_url: '',
      notes: '',
    },
  });

  return (
    <form
      onSubmit={form.handleSubmit((v) =>
        onSubmit(v as unknown as EoCertificateCreateInput),
      )}
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
          label="Limit amount (USD)"
          required
          inputMode="decimal"
          {...form.register('limit_amount')}
          error={form.formState.errors.limit_amount?.message}
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Input
          label="Retroactive date"
          type="date"
          {...form.register('retroactive_date')}
        />
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
          Create E&amp;O cert
        </Button>
      </div>
    </form>
  );
}

export default function EoCertificates(): JSX.Element {
  return (
    <ResourcePage<EoCertificate, EoCertificateCreateInput>
      title="Errors & Omissions certificates"
      description="Professional liability coverage for each supplier."
      pluralNoun="E&O certificates"
      singularNoun="E&O certificate"
      emptyIcon={ShieldCheck}
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
      useList={eoCertificatesHooks.useList}
      useCreate={eoCertificatesHooks.useCreate}
      renderForm={(args) => <EoForm {...args} />}
    />
  );
}
