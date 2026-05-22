import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { UserPlus } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { registerSchema, type RegisterFormValues } from '@/schemas/auth';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { toast } from '@/lib/toast';

export default function Register(): JSX.Element {
  const { register: registerUser } = useAuth();
  const navigate = useNavigate();

  const form = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      tenant_name: '',
      full_name: '',
      email: '',
      password: '',
    },
    mode: 'onBlur',
  });

  async function onSubmit(values: RegisterFormValues): Promise<void> {
    try {
      await registerUser(values);
      toast.success('Account created.');
      navigate('/dashboard', { replace: true });
    } catch (err) {
      toast.error(err, 'Registration failed');
    }
  }

  const submitting = form.formState.isSubmitting;

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-10 dark:bg-slate-950">
      <div className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="mb-6 flex items-center gap-2">
          <UserPlus className="h-6 w-6 text-slate-700 dark:text-slate-200" aria-hidden="true" />
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
            Create your Once tenant
          </h1>
        </div>
        <p className="mb-6 text-sm text-slate-500 dark:text-slate-400">
          One submission. Many carriers. Forever provable.
        </p>

        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <Input
            label="Organization (MGA) name"
            autoComplete="organization"
            required
            disabled={submitting}
            {...form.register('tenant_name')}
            error={form.formState.errors.tenant_name?.message}
          />
          <Input
            label="Your full name"
            autoComplete="name"
            required
            disabled={submitting}
            {...form.register('full_name')}
            error={form.formState.errors.full_name?.message}
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
            hint="Minimum 8 characters."
            disabled={submitting}
            {...form.register('password')}
            error={form.formState.errors.password?.message}
          />
          <Button type="submit" fullWidth loading={submitting} disabled={submitting}>
            {submitting ? 'Creating account…' : 'Create account'}
          </Button>
        </form>

        <p className="mt-6 text-sm text-slate-600 dark:text-slate-400">
          Already have an account?{' '}
          <Link
            to="/login"
            className="font-medium text-slate-900 underline hover:no-underline dark:text-slate-200"
          >
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
