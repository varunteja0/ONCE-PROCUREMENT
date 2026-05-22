// --- L3.6 onboarding ---
import { useNavigate } from 'react-router-dom';
import StepShell from '@/components/onboarding/StepShell';
import { Button } from '@/components/ui/Button';
import { toast } from '@/lib/toast';
import { onboarding } from '@/services/onboardingApi';

export default function StepChoosePlan(): JSX.Element {
  const navigate = useNavigate();

  async function skip(): Promise<void> {
    try {
      await onboarding.skipStep('plan');
      navigate('/onboarding/portal');
    } catch (err) {
      toast.error(err, 'Could not skip this step');
    }
  }

  function gotoPricing(): void {
    // Pricing lives in C3 (L3.5 billing). The user can return to /onboarding
    // afterwards via the wizard URL.
    window.location.assign('/pricing?from=onboarding');
  }

  return (
    <StepShell
      title="Choose a plan"
      description="Start free, upgrade when you’re ready. You can always change later."
    >
      <div className="space-y-4">
        <div className="rounded-lg border border-slate-200 p-4 dark:border-slate-800">
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
            Free
          </h3>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
            Up to 25 submissions / month. Full audit ledger. No card required.
          </p>
          <Button type="button" className="mt-3" onClick={skip}>
            Stay on Free
          </Button>
        </div>
        <div className="rounded-lg border border-slate-200 p-4 dark:border-slate-800">
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
            Paid plans
          </h3>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
            Higher volume, dedicated portals, priority support.
          </p>
          <Button variant="outline" type="button" className="mt-3" onClick={gotoPricing}>
            View pricing
          </Button>
        </div>
        <button
          type="button"
          onClick={skip}
          className="text-sm text-slate-500 underline hover:no-underline dark:text-slate-400"
        >
          Skip — I’ll pick a plan later
        </button>
      </div>
    </StepShell>
  );
}
// --- /L3.6 onboarding ---
