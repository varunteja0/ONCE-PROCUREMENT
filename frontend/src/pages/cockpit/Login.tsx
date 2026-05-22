import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Shield } from 'lucide-react';
import { useCockpit } from '@/hooks/useCockpit';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { toast } from '@/lib/toast';

interface LocationState {
  from?: string;
}

export default function CockpitLogin(): JSX.Element {
  const { login } = useCockpit();
  const navigate = useNavigate();
  const location = useLocation();

  const redirectTo =
    (location.state as LocationState | null)?.from ?? '/cockpit';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [totp, setTotp] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    setSubmitting(true);
    try {
      await login({
        email,
        password,
        totp_code: totp.length > 0 ? totp : undefined,
      });
      toast.success('Cockpit unlocked.');
      navigate(redirectTo, { replace: true });
    } catch (err) {
      toast.error(err, 'Cockpit login failed');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-amber-50 px-4 dark:bg-slate-950">
      <div
        className="w-full max-w-md rounded-lg border border-amber-300 bg-white p-8 shadow-sm dark:border-amber-800 dark:bg-slate-900"
        data-testid="cockpit-login"
      >
        <div className="mb-6 flex items-center gap-2">
          <Shield className="h-6 w-6 text-amber-700 dark:text-amber-300" aria-hidden="true" />
          <h1 className="text-2xl font-semibold text-amber-900 dark:text-amber-100">
            Founder Cockpit
          </h1>
        </div>
        <p className="mb-6 text-sm text-slate-500 dark:text-slate-400">
          Operator surface — all actions are recorded to the cockpit audit log.
        </p>

        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <Input
            label="Operator email"
            type="email"
            autoComplete="email"
            required
            disabled={submitting}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Input
            label="Password"
            type="password"
            autoComplete="current-password"
            required
            disabled={submitting}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <Input
            label="TOTP (if enabled)"
            type="text"
            autoComplete="one-time-code"
            inputMode="numeric"
            disabled={submitting}
            value={totp}
            onChange={(e) => setTotp(e.target.value)}
          />
          <Button type="submit" fullWidth loading={submitting} disabled={submitting}>
            {submitting ? 'Signing in…' : 'Enter cockpit'}
          </Button>
        </form>
      </div>
    </div>
  );
}
