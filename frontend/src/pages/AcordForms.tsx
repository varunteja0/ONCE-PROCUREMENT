import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { FileText } from 'lucide-react';
import { ResourcePage } from '@/components/ResourcePage';
import { SupplierPicker } from '@/components/SupplierPicker';
import {
  Button,
  Input,
  Select,
  Textarea,
  DateDisplay,
} from '@/components/ui';
import { acordFormsHooks } from '@/hooks/useArtifacts';
import {
  acordFormSchema,
  acordFormTypes,
  type AcordFormValues,
} from '@/schemas/artifacts';
import type { AcordForm, AcordFormCreateInput } from '@/types/api';

function AcordFormFields({
  onSubmit,
  submitting,
  onCancel,
}: {
  onSubmit: (input: AcordFormCreateInput) => Promise<void>;
  submitting: boolean;
  onCancel: () => void;
}): JSX.Element {
  const form = useForm<AcordFormValues>({
    resolver: zodResolver(acordFormSchema),
    defaultValues: {
      supplier_id: '',
      form_type: '125',
      payload: '{\n  \n}',
      pdf_url: '',
    },
  });

  async function handleSubmit(values: AcordFormValues): Promise<void> {
    const parsed = JSON.parse(values.payload) as Record<string, unknown>;
    const input: AcordFormCreateInput = {
      supplier_id: values.supplier_id,
      form_type: values.form_type,
      payload: parsed,
      pdf_url: values.pdf_url ?? null,
    };
    await onSubmit(input);
  }

  return (
    <form
      onSubmit={form.handleSubmit(handleSubmit)}
      className="space-y-3"
      noValidate
    >
      <SupplierPicker
        label="Supplier"
        required
        {...form.register('supplier_id')}
        error={form.formState.errors.supplier_id?.message}
      />
      <Select
        label="ACORD form type"
        required
        options={acordFormTypes.map((t) => ({ value: t, label: `ACORD ${t}` }))}
        {...form.register('form_type')}
        error={form.formState.errors.form_type?.message}
      />
      <Textarea
        label="Payload (JSON)"
        rows={8}
        required
        className="font-mono text-xs"
        hint="Must be a valid JSON object."
        {...form.register('payload')}
        error={form.formState.errors.payload?.message}
      />
      <Input label="PDF URL" type="url" {...form.register('pdf_url')} />
      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" loading={submitting}>
          Create ACORD form
        </Button>
      </div>
    </form>
  );
}

export default function AcordForms(): JSX.Element {
  return (
    <ResourcePage<AcordForm, AcordFormCreateInput>
      title="ACORD forms"
      description="Standardized commercial insurance application data."
      pluralNoun="ACORD forms"
      singularNoun="ACORD form"
      emptyIcon={FileText}
      rowKey={(r) => r.id}
      columns={[
        {
          key: 'supplier',
          header: 'Supplier',
          cell: (r) => (
            <span className="font-mono text-xs">{r.supplier_id.slice(0, 8)}</span>
          ),
        },
        {
          key: 'type',
          header: 'Form',
          cell: (r) => `ACORD ${r.form_type}`,
        },
        {
          key: 'created',
          header: 'Created',
          cell: (r) => <DateDisplay value={r.created_at} />,
        },
      ]}
      useList={acordFormsHooks.useList}
      useCreate={acordFormsHooks.useCreate}
      renderForm={(args) => <AcordFormFields {...args} />}
    />
  );
}
