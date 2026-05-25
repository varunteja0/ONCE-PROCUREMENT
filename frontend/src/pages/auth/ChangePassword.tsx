import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { KeyRound } from 'lucide-react';
import { useState } from 'react';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { toast } from '@/lib/toast';
import { api, extractErrorMessage, isApiError } from '@/services/api';
import {
  passwordChangeSchema,
  type PasswordChangeFormValues,
} from '@/schemas/auth';
import { scorePassword } from '@/lib/passwordStrength';
import { useAuth } from '@/hooks/useAuth';

const SEGMENT_COLORS: ReadonlyArray<string> = [
  'bg-rose-500',
  'bg-amber-500',
  'bg-yellow-500',
  'bg-lime-500',
  'bg-emerald-500',
];

function StrengthMeter({ password, email }: { password: string; email?: string | null }): JSX.Element {
  const result = scorePassword(password, { email });
  const filled = password.length === 0 ? 0 : result.score + 1;
  return (
    <div className="mt-1" aria-live="polite">
      <div className="flex gap-1" role="presentation">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className={`h-1.5 flex-1 rounded ${
              password.length > 0 && i < filled
                ? SEGMENT_COLORS[result.score]
                : 'bg-slate-200 dark:bg-slate-700'
            }`}
          />
        ))}
      </div>
      {password.length > 0 ? (
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
          Strength: <span className="font-medium">{result.label}</span>
          {result.reasons.length > 0 ? ` — ${result.reasons[0]}` : ''}
        </p>
      ) : null}
    </div>
  );
}

export default function ChangePassword(): JSX.Element {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [notImplemented, setNotImplemented] = useState<string | null>(null);

  const form = useForm<PasswordChangeFormValues>({
    resolver: zodResolver(passwordChangeSchema),
    defaultValues: {
      current_password: '',
      new_password: '',
      confirm_password: '',
    },
    mode: 'onBlur',
  });

  const newPw = form.watch('new_password');
  const score = scorePassword(newPw, { email: user?.email ?? null }).score;

  async function onSubmit(values: PasswordChangeFormValues): Promise<void> {
    setNotImplemented(null);
    try {
      // BACKEND-COUPLED: depends on POST /auth/change-password being implemented.
      await api.post('/auth/change-password', values);
      toast.success('Password updated.');
      navigate('/settings', { replace: true });
    } catch (err) {
      if (isApiError(err) && err.response?.status === 404) {
        // BACKEND-COUPLED: backend endpoint not yet implemented.
        setNotImplemented('Coming soon — backend endpoint pending.');
        return;
      }
      toast.error(extractErrorMessage(err, 'Could not update password'));
    }
  }

  const submitting = form.formState.isSubmitting;
  const disableSubmit = submitting || (newPw.length > 0 && score < 2);

  return (
    <div className="mx-auto max-w-md space-y-6">
      <header className="flex items-center gap-2">
        <KeyRound className="h-5 w-5 text-slate-700 dark:text-slate-200" aria-hidden="true" />
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
          Change password
        </h1>
      </header>

      {notImplemented ? (
        <div
          role="status"
          className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200"
        >
          {notImplemented}
        </div>
      ) : null}

      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <Input
          label="Current password"
          type="password"
          autoComplete="current-password"
          required
          disabled={submitting}
          {...form.register('current_password')}
          error={form.formState.errors.current_password?.message}
        />
        <div>
          <Input
            label="New password"
            type="password"
            autoComplete="new-password"
            required
            disabled={submitting}
            {...form.register('new_password')}
            error={form.formState.errors.new_password?.message}
          />
          <StrengthMeter password={newPw} email={user?.email ?? null} />
        </div>
        <Input
          label="Confirm new password"
          type="password"
          autoComplete="new-password"
          required
          disabled={submitting}
          {...form.register('confirm_password')}
          error={form.formState.errors.confirm_password?.message}
        />
        <div className="flex justify-end gap-2">
          <Button
            type="button"
            variant="ghost"
            onClick={() => navigate('/settings')}
            disabled={submitting}
          >
            Cancel
          </Button>
          <Button type="submit" loading={submitting} disabled={disableSubmit}>
            {submitting ? 'Saving…' : 'Update password'}
          </Button>
        </div>
      </form>
    </div>
  );
}
