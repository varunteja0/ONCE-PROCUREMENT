import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { KeyRound } from 'lucide-react';
import { useState } from 'react';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { toast } from '@/lib/toast';
import { api, extractErrorMessage, isApiError } from '@/services/api';
import {
  resetPasswordSchema,
  type ResetPasswordFormValues,
} from '@/schemas/auth';
import { scorePassword } from '@/lib/passwordStrength';

const SEGMENT_COLORS: ReadonlyArray<string> = [
  'bg-rose-500',
  'bg-amber-500',
  'bg-yellow-500',
  'bg-lime-500',
  'bg-emerald-500',
];

function StrengthMeter({ password }: { password: string }): JSX.Element {
  const result = scorePassword(password);
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

export default function ResetPassword(): JSX.Element {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get('token') ?? '';
  const [notImplemented, setNotImplemented] = useState<string | null>(null);

  const form = useForm<ResetPasswordFormValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { new_password: '', confirm_password: '' },
    mode: 'onBlur',
  });

  const newPw = form.watch('new_password');
  const score = scorePassword(newPw).score;

  async function onSubmit(values: ResetPasswordFormValues): Promise<void> {
    setNotImplemented(null);
    try {
      // BACKEND-COUPLED: depends on POST /auth/reset-password being implemented.
      await api.post(
        '/auth/reset-password',
        { token, new_password: values.new_password },
        { _onceSkipAuth: true },
      );
      toast.success('Password reset. Please sign in.');
      navigate('/login', { replace: true });
    } catch (err) {
      if (isApiError(err) && err.response?.status === 404) {
        // BACKEND-COUPLED: backend endpoint not yet implemented.
        setNotImplemented('Coming soon — backend endpoint pending.');
        return;
      }
      toast.error(extractErrorMessage(err, 'Could not reset password'));
    }
  }

  const submitting = form.formState.isSubmitting;
  const disableSubmit =
    submitting || token.length === 0 || (newPw.length > 0 && score < 2);

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 dark:bg-slate-950">
      <div className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="mb-6 flex items-center gap-2">
          <KeyRound className="h-6 w-6 text-slate-700 dark:text-slate-200" aria-hidden="true" />
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
            Reset your password
          </h1>
        </div>

        {token.length === 0 ? (
          <div
            role="alert"
            className="mb-4 rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200"
          >
            Missing or invalid reset token. Request a new link.
          </div>
        ) : null}

        {notImplemented ? (
          <div
            role="status"
            className="mb-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200"
          >
            {notImplemented}
          </div>
        ) : null}

        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
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
            <StrengthMeter password={newPw} />
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
          <Button type="submit" fullWidth loading={submitting} disabled={disableSubmit}>
            {submitting ? 'Resetting…' : 'Reset password'}
          </Button>
        </form>

        <p className="mt-6 text-sm text-slate-600 dark:text-slate-400">
          <Link
            to="/login"
            className="font-medium text-slate-900 underline hover:no-underline dark:text-slate-200"
          >
            Back to sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
