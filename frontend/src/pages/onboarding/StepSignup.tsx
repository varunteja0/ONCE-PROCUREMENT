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
import { useOnboardingStore } from '@/store/onboardingStore';

const schema = z.object({
  company_name: z.string().trim().min(1, 'Required'),
  email: z.string().trim().email('Enter a valid email'),
  password: z.string().min(12, 'Use at least 12 characters'),
  website_url: z.string().optional(),
});
type FormValues = z.infer<typeof schema>;

export default function StepSignup(): JSX.Element {
  const navigate = useNavigate();
  const setDraft = useOnboardingStore((s) => s.setDraft);
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { company_name: '', email: '', password: '', website_url: '' },
    mode: 'onBlur',
  });

  async function onSubmit(values: FormValues): Promise<void> {
    try {
      const r = await onboarding.start(values);
      setDraft({
        email: values.email,
        companyName: values.company_name,
        tenantId: r.tenant_id,
        devVerificationCode: r.dev_verification_code ?? null,
      });
      toast.success('Check your email for a 6-digit code.');
      navigate('/onboarding/verify-email');
    } catch (err) {
      toast.error(err, 'Could not create your account');
    }
  }

  const submitting = form.formState.isSubmitting;

  return (
    <StepShell
      title="Create your Once account"
      description="One submission. Many carriers. Forever provable."
    >
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <Input
          label="Company / MGA name"
          autoComplete="organization"
          required
          disabled={submitting}
          {...form.register('company_name')}
          error={form.formState.errors.company_name?.message}
        />
        <Input
          label="Work email"
          type="email"
          autoComplete="email"
          required
          disabled={submitting}
          {...form.register('email')}
          error={form.formState.errors.email?.message}
        />
        <Input
          label="Password"
          type="password"
          autoComplete="new-password"
          required
          hint="Use 12+ characters. Avoid common words."
          disabled={submitting}
          {...form.register('password')}
          error={form.formState.errors.password?.message}
        />
        {/* Honeypot — keep hidden from real users. */}
        <input
          type="text"
          tabIndex={-1}
          autoComplete="off"
          aria-hidden="true"
          className="hidden"
          {...form.register('website_url')}
        />
        <Button type="submit" fullWidth loading={submitting} disabled={submitting}>
          {submitting ? 'Creating account…' : 'Continue'}
        </Button>
      </form>
    </StepShell>
  );
}
// --- /L3.6 onboarding ---
