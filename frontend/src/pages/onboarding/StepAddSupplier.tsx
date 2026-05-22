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
  fein: z.string().trim().optional(),
  state: z
    .string()
    .trim()
    .length(2, 'Use the 2-letter state code')
    .transform((v) => v.toUpperCase()),
  primary_email: z
    .union([z.literal(''), z.string().trim().email('Enter a valid email')])
    .optional(),
});
type FormValues = z.infer<typeof schema>;

export default function StepAddSupplier(): JSX.Element {
  const navigate = useNavigate();
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { legal_name: '', fein: '', state: '', primary_email: '' },
    mode: 'onBlur',
  });

  async function onSubmit(values: FormValues): Promise<void> {
    try {
      await onboarding.addSupplier({
        legal_name: values.legal_name,
        state: values.state,
        fein: values.fein || undefined,
        primary_email: values.primary_email || undefined,
      });
      toast.success('Supplier added.');
      navigate('/onboarding/submission');
    } catch (err) {
      toast.error(err, 'Could not add that supplier');
    }
  }

  async function skip(): Promise<void> {
    try {
      await onboarding.skipStep('supplier');
      navigate('/onboarding/submission');
    } catch (err) {
      toast.error(err, 'Could not skip this step');
    }
  }

  const submitting = form.formState.isSubmitting;

  return (
    <StepShell
      title="Add your first supplier"
      description="Suppliers are the producing agencies you submit on behalf of. You can add more later."
    >
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <Input
          label="Supplier legal name"
          required
          disabled={submitting}
          {...form.register('legal_name')}
          error={form.formState.errors.legal_name?.message}
        />
        <Input
          label="EIN (optional)"
          disabled={submitting}
          {...form.register('fein')}
          error={form.formState.errors.fein?.message}
        />
        <Input
          label="State"
          required
          placeholder="CA"
          maxLength={2}
          disabled={submitting}
          {...form.register('state')}
          error={form.formState.errors.state?.message}
        />
        <Input
          label="Primary contact email (optional)"
          type="email"
          disabled={submitting}
          {...form.register('primary_email')}
          error={form.formState.errors.primary_email?.message}
        />
        <div className="flex items-center gap-3">
          <Button type="submit" loading={submitting} disabled={submitting}>
            {submitting ? 'Saving…' : 'Add supplier & continue'}
          </Button>
          <Button type="button" variant="ghost" onClick={skip} disabled={submitting}>
            Skip for now
          </Button>
        </div>
      </form>
    </StepShell>
  );
}
// --- /L3.6 onboarding ---
