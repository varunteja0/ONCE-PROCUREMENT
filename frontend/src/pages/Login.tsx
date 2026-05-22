import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { LogIn } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { loginSchema, type LoginFormValues } from '@/schemas/auth';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { toast } from '@/lib/toast';

interface LocationState {
  from?: string;
}

export default function Login(): JSX.Element {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const redirectTo =
    (location.state as LocationState | null)?.from ?? '/dashboard';

  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' },
    mode: 'onBlur',
  });

  async function onSubmit(values: LoginFormValues): Promise<void> {
    try {
      await login({ email: values.email, password: values.password });
      toast.success('Welcome back.');
      navigate(redirectTo, { replace: true });
    } catch (err) {
      toast.error(err, 'Login failed');
    }
  }

  const submitting = form.formState.isSubmitting;

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 dark:bg-slate-950">
      <div className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="mb-6 flex items-center gap-2">
          <LogIn className="h-6 w-6 text-slate-700 dark:text-slate-200" aria-hidden="true" />
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
            Sign in to Once
          </h1>
        </div>
        <p className="mb-6 text-sm text-slate-500 dark:text-slate-400">
          Submit once. Prove it forever.
        </p>

        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <Input
            label="Email"
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
            autoComplete="current-password"
            required
            disabled={submitting}
            {...form.register('password')}
            error={form.formState.errors.password?.message}
          />
          <Button type="submit" fullWidth loading={submitting} disabled={submitting}>
            {submitting ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>

        <p className="mt-6 text-sm text-slate-600 dark:text-slate-400">
          New to Once?{' '}
          <Link
            to="/register"
            className="font-medium text-slate-900 underline hover:no-underline dark:text-slate-200"
          >
            Create an account
          </Link>
        </p>
      </div>
    </div>
  );
}
