// --- L3.6 onboarding ---
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import StepShell from '@/components/onboarding/StepShell';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { toast } from '@/lib/toast';
import { onboarding } from '@/services/onboardingApi';

const schema = z.object({
  legal_name: z.string().trim().min(1, 'Required'),
  fein: z
    .string()
    .trim()
    .min(9, 'Enter a valid EIN')
    .max(32),
  primary_state: z
    .string()
    .trim()
    .length(2, 'Use the 2-letter state code')
    .transform((v) => v.toUpperCase()),
  employees: z
    .union([z.literal(''), z.coerce.number().int().nonnegative()])
    .optional(),
  gwp_band: z.string().trim().optional(),
});
type FormValues = z.infer<typeof schema>;

export default function StepCompanyProfile(): JSX.Element {
  const navigate = useNavigate();
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      legal_name: '',
      fein: '',
      primary_state: '',
      employees: '',
      gwp_band: '',
    },
    mode: 'onBlur',
  });

  async function onSubmit(values: FormValues): Promise<void> {
    try {
      await onboarding.companyProfile({
        legal_name: values.legal_name,
        fein: values.fein,
        primary_state: values.primary_state,
        employees:
          typeof values.employees === 'number' ? values.employees : undefined,
        gwp_band: values.gwp_band || undefined,
      });
      toast.success('Company profile saved.');
      navigate('/onboarding/plan');
    } catch (err) {
      toast.error(err, 'Could not save your profile');
    }
  }

  const submitting = form.formState.isSubmitting;

  return (
    <StepShell
      title="Tell us about your MGA"
      description="We use this to pre-fill ACORDs and producer licensing checks."
    >
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <Input
          label="Legal entity name"
          required
          disabled={submitting}
          {...form.register('legal_name')}
          error={form.formState.errors.legal_name?.message}
        />
        <Input
          label="Federal EIN"
          required
          placeholder="12-3456789"
          disabled={submitting}
          {...form.register('fein')}
          error={form.formState.errors.fein?.message}
        />
        <Input
          label="Primary state"
          required
          placeholder="CA"
          maxLength={2}
          disabled={submitting}
          {...form.register('primary_state')}
          error={form.formState.errors.primary_state?.message}
        />
        <Input
          label="Employees (optional)"
          type="number"
          min={0}
          disabled={submitting}
          {...form.register('employees')}
          error={form.formState.errors.employees?.message}
        />
        <Input
          label="Annual GWP band (optional)"
          placeholder="< $5M / $5M–$25M / > $25M"
          disabled={submitting}
          {...form.register('gwp_band')}
          error={form.formState.errors.gwp_band?.message}
        />
        <Button type="submit" fullWidth loading={submitting} disabled={submitting}>
          {submitting ? 'Saving…' : 'Save and continue'}
        </Button>
      </form>
    </StepShell>
  );
}
// --- /L3.6 onboarding ---
