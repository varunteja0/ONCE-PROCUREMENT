import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { ListTree } from 'lucide-react';
import { ResourcePage } from '@/components/ResourcePage';
import { SupplierPicker } from '@/components/SupplierPicker';
import { Button, Input, Textarea, DateDisplay } from '@/components/ui';
import { riskSchedulesHooks } from '@/hooks/useArtifacts';
import {
  riskScheduleSchema,
  type RiskScheduleFormValues,
} from '@/schemas/artifacts';
import type { RiskSchedule, RiskScheduleCreateInput } from '@/types/api';

function RiskScheduleForm({
  onSubmit,
  submitting,
  onCancel,
}: {
  onSubmit: (input: RiskScheduleCreateInput) => Promise<void>;
  submitting: boolean;
  onCancel: () => void;
}): JSX.Element {
  const form = useForm<RiskScheduleFormValues>({
    resolver: zodResolver(riskScheduleSchema),
    defaultValues: {
      supplier_id: '',
      line_of_business: '',
      payload: '{\n  \n}',
      effective_date: '',
      notes: '',
    },
  });

  async function handleSubmit(values: RiskScheduleFormValues): Promise<void> {
    const parsed = JSON.parse(values.payload) as Record<string, unknown>;
    const input: RiskScheduleCreateInput = {
      supplier_id: values.supplier_id,
      line_of_business: values.line_of_business,
      payload: parsed,
      effective_date: values.effective_date ?? null,
      notes: values.notes ?? null,
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
      <Input
        label="Line of business"
        required
        {...form.register('line_of_business')}
        error={form.formState.errors.line_of_business?.message}
      />
      <Textarea
        label="Payload (JSON)"
        rows={8}
        required
        className="font-mono text-xs"
        hint="Schedule details as a JSON object."
        {...form.register('payload')}
        error={form.formState.errors.payload?.message}
      />
      <Input
        label="Effective date"
        type="date"
        {...form.register('effective_date')}
      />
      <Textarea label="Notes" rows={2} {...form.register('notes')} />
      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" loading={submitting}>
          Create schedule
        </Button>
      </div>
    </form>
  );
}

export default function RiskSchedules(): JSX.Element {
  return (
    <ResourcePage<RiskSchedule, RiskScheduleCreateInput>
      title="Risk schedules"
      description="Per-line-of-business risk schedules per supplier."
      pluralNoun="risk schedules"
      singularNoun="risk schedule"
      emptyIcon={ListTree}
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
          key: 'lob',
          header: 'Line of business',
          cell: (r) => r.line_of_business,
        },
        {
          key: 'effective',
          header: 'Effective',
          cell: (r) => <DateDisplay value={r.effective_date} />,
        },
      ]}
      useList={riskSchedulesHooks.useList}
      useCreate={riskSchedulesHooks.useCreate}
      renderForm={(args) => <RiskScheduleForm {...args} />}
    />
  );
}
