// --- L3.6 onboarding ---
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import StepShell from '@/components/onboarding/StepShell';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Select';
import { toast } from '@/lib/toast';
import { api, type Portal, type PortalListResponse } from '@/services/api';
import { onboarding } from '@/services/onboardingApi';

const schema = z.object({
  portal_id: z.string().min(1, 'Pick a portal'),
  username: z.string().trim().min(1, 'Required'),
  password: z.string().min(1, 'Required'),
});
type FormValues = z.infer<typeof schema>;

export default function StepConnectPortal(): JSX.Element {
  const navigate = useNavigate();
  const [portals, setPortals] = useState<Portal[]>([]);
  const [loadingPortals, setLoadingPortals] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const r = await api.get<PortalListResponse>('/portals', {
          params: { is_supported: true, limit: 50 },
        });
        if (!cancelled) setPortals(r.data.items);
      } catch {
        if (!cancelled) setPortals([]);
      } finally {
        if (!cancelled) setLoadingPortals(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { portal_id: '', username: '', password: '' },
    mode: 'onBlur',
  });

  async function onSubmit(values: FormValues): Promise<void> {
    try {
      await onboarding.connectPortal(values);
      toast.success('Portal connected.');
      navigate('/onboarding/supplier');
    } catch (err) {
      toast.error(err, 'Could not connect that portal');
    }
  }

  async function skip(): Promise<void> {
    try {
      await onboarding.skipStep('portal');
      navigate('/onboarding/supplier');
    } catch (err) {
      toast.error(err, 'Could not skip this step');
    }
  }

  const submitting = form.formState.isSubmitting;

  return (
    <StepShell
      title="Connect a carrier portal (optional)"
      description="Credentials are encrypted at rest. You can change or remove them any time from Settings."
    >
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <Select
          label="Portal"
          required
          disabled={submitting || loadingPortals}
          {...form.register('portal_id')}
          error={form.formState.errors.portal_id?.message}
          placeholder={loadingPortals ? 'Loading portals…' : 'Select a portal'}
          options={portals.map((p) => ({ value: p.id, label: p.display_name }))}
        />
        <Input
          label="Portal username"
          autoComplete="username"
          required
          disabled={submitting}
          {...form.register('username')}
          error={form.formState.errors.username?.message}
        />
        <Input
          label="Portal password"
          type="password"
          autoComplete="current-password"
          required
          disabled={submitting}
          {...form.register('password')}
          error={form.formState.errors.password?.message}
        />
        <div className="flex items-center gap-3">
          <Button type="submit" loading={submitting} disabled={submitting}>
            {submitting ? 'Connecting…' : 'Connect & continue'}
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
