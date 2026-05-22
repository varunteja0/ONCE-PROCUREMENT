// --- L3.6 onboarding ---
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import StepShell from '@/components/onboarding/StepShell';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { toast } from '@/lib/toast';
import { onboarding, onboardingTokenStorage } from '@/services/onboardingApi';
import { tokenStorage } from '@/services/api';
import { useOnboardingStore } from '@/store/onboardingStore';

const schema = z.object({
  code: z
    .string()
    .trim()
    .regex(/^\d{6}$/u, 'Enter the 6-digit code from your inbox'),
});
type FormValues = z.infer<typeof schema>;

export default function StepVerifyEmail(): JSX.Element {
  const navigate = useNavigate();
  const draft = useOnboardingStore((s) => s.draft);
  const setDraft = useOnboardingStore((s) => s.setDraft);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { code: draft.devVerificationCode ?? '' },
    mode: 'onBlur',
  });

  async function onSubmit(values: FormValues): Promise<void> {
    try {
      const r = await onboarding.verifyEmail(values.code);
      tokenStorage.setPair({
        access_token: r.access_token,
        refresh_token: r.refresh_token,
        token_type: 'bearer',
      });
      onboardingTokenStorage.clear();
      setDraft({ devVerificationCode: null });
      toast.success('Email verified.');
      navigate('/onboarding/profile');
    } catch (err) {
      toast.error(err, 'Could not verify that code');
    }
  }

  const submitting = form.formState.isSubmitting;

  return (
    <StepShell
      title="Verify your email"
      description={
        draft.email
          ? `We emailed a 6-digit code to ${draft.email}. It expires in 30 minutes.`
          : 'Enter the 6-digit code we sent to your inbox.'
      }
    >
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <Input
          label="Verification code"
          inputMode="numeric"
          autoComplete="one-time-code"
          required
          disabled={submitting}
          {...form.register('code')}
          error={form.formState.errors.code?.message}
        />
        {draft.devVerificationCode ? (
          <p className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
            Dev mode: code <strong>{draft.devVerificationCode}</strong> is pre-filled.
          </p>
        ) : null}
        <Button type="submit" fullWidth loading={submitting} disabled={submitting}>
          {submitting ? 'Verifying…' : 'Verify and continue'}
        </Button>
      </form>
    </StepShell>
  );
}
// --- /L3.6 onboarding ---
