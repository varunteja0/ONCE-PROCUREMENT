// --- L3.6 onboarding ---
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle2 } from 'lucide-react';
import StepShell from '@/components/onboarding/StepShell';
import { Button } from '@/components/ui/Button';
import { toast } from '@/lib/toast';
import { onboarding } from '@/services/onboardingApi';
import { clearOnboardingSession } from '@/hooks/useOnboarding';

export default function StepDone(): JSX.Element {
  const navigate = useNavigate();
  const [dashboardUrl, setDashboardUrl] = useState('/dashboard');

  useEffect(() => {
    void (async () => {
      try {
        const r = await onboarding.complete();
        setDashboardUrl(r.dashboard_url || '/dashboard');
      } catch (err) {
        toast.error(err, 'Could not finalise onboarding');
      }
    })();
  }, []);

  function goToDashboard(): void {
    clearOnboardingSession();
    navigate(dashboardUrl, { replace: true });
  }

  return (
    <StepShell
      title="You’re live on Once"
      description="One submission. Many carriers. Forever provable."
    >
      <div className="space-y-5">
        <div className="flex items-center gap-3 text-emerald-600 dark:text-emerald-400">
          <CheckCircle2 className="h-8 w-8" aria-hidden="true" />
          <p className="text-lg font-semibold">Welcome aboard.</p>
        </div>
        <ul className="space-y-2 text-sm text-slate-700 dark:text-slate-300">
          <li>✓ Your tenant is provisioned and email-verified.</li>
          <li>✓ Company profile saved.</li>
          <li>✓ First supplier added.</li>
          <li>✓ Submission queued — track it from the dashboard.</li>
        </ul>
        <div className="rounded-md bg-slate-50 p-4 text-sm dark:bg-slate-800">
          <p className="font-medium text-slate-900 dark:text-slate-100">Next steps</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-600 dark:text-slate-400">
            <li>Invite teammates from Settings → Users.</li>
            <li>Upload COIs, producer licences, and loss runs under Documents.</li>
            <li>Connect additional carrier portals.</li>
          </ul>
        </div>
        <Button onClick={goToDashboard} fullWidth>
          Go to dashboard
        </Button>
      </div>
    </StepShell>
  );
}
// --- /L3.6 onboarding ---
