import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { FileBarChart2 } from 'lucide-react';
import { ResourcePage } from '@/components/ResourcePage';
import { SupplierPicker } from '@/components/SupplierPicker';
import { Button, Input, Textarea, DateDisplay, MoneyDisplay } from '@/components/ui';
import { lossRunsHooks } from '@/hooks/useArtifacts';
import { lossRunSchema, type LossRunFormValues } from '@/schemas/artifacts';
import type { LossRun, LossRunCreateInput } from '@/types/api';

function toCreateInput(v: LossRunFormValues): LossRunCreateInput {
  return {
    supplier_id: v.supplier_id,
    period_start: v.period_start,
    period_end: v.period_end,
    carrier: v.carrier ?? null,
    total_claims: v.total_claims ?? null,
    total_incurred: v.total_incurred ?? null,
    file_url: v.file_url ?? null,
    notes: v.notes ?? null,
  };
}

function LossRunForm({
  onSubmit,
  submitting,
  onCancel,
}: {
  onSubmit: (input: LossRunCreateInput) => Promise<void>;
  submitting: boolean;
  onCancel: () => void;
}): JSX.Element {
  const form = useForm<LossRunFormValues>({
    resolver: zodResolver(lossRunSchema),
    defaultValues: {
      supplier_id: '',
      period_start: '',
      period_end: '',
      carrier: '',
      total_claims: undefined,
      total_incurred: '',
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
          label="Period start"
          type="date"
          required
          {...form.register('period_start')}
          error={form.formState.errors.period_start?.message}
        />
        <Input
          label="Period end"
          type="date"
          required
          {...form.register('period_end')}
          error={form.formState.errors.period_end?.message}
        />
      </div>
      <Input label="Carrier" {...form.register('carrier')} />
      <div className="grid grid-cols-2 gap-3">
        <Input
          label="Total claims"
          type="number"
          min={0}
          {...form.register('total_claims')}
          error={form.formState.errors.total_claims?.message as string | undefined}
        />
        <Input
          label="Total incurred (USD)"
          inputMode="decimal"
          {...form.register('total_incurred')}
        />
      </div>
      <Input label="File URL" type="url" {...form.register('file_url')} />
      <Textarea label="Notes" rows={2} {...form.register('notes')} />
      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" loading={submitting}>
          Create loss run
        </Button>
      </div>
    </form>
  );
}

export default function LossRuns(): JSX.Element {
  return (
    <ResourcePage<LossRun, LossRunCreateInput>
      title="Loss runs"
      description="Historical claims experience by supplier and period."
      pluralNoun="loss runs"
      singularNoun="loss run"
      emptyIcon={FileBarChart2}
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
          key: 'period',
          header: 'Period',
          cell: (r) => (
            <span>
              <DateDisplay value={r.period_start} /> –{' '}
              <DateDisplay value={r.period_end} />
            </span>
          ),
        },
        {
          key: 'claims',
          header: 'Claims',
          align: 'right',
          cell: (r) => r.total_claims ?? '—',
        },
        {
          key: 'incurred',
          header: 'Incurred',
          align: 'right',
          cell: (r) => <MoneyDisplay value={r.total_incurred} />,
        },
      ]}
      useList={lossRunsHooks.useList}
      useCreate={lossRunsHooks.useCreate}
      renderForm={(args) => <LossRunForm {...args} />}
    />
  );
}
