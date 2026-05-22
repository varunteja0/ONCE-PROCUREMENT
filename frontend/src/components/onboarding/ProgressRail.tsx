// --- L3.6 onboarding ---
import { Check, Circle, MinusCircle } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { cn } from '@/lib/cn';
import { ONBOARDING_STEPS } from '@/store/onboardingStore';
import { useOnboardingStore } from '@/store/onboardingStore';

export default function ProgressRail(): JSX.Element {
  const location = useLocation();
  const completed = useOnboardingStore((s) => s.completedSteps);
  const skipped = useOnboardingStore((s) => s.skippedSteps);

  return (
    <nav aria-label="Onboarding progress" className="space-y-1">
      <h2 className="px-3 pb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        Get started
      </h2>
      <ol className="space-y-1">
        {ONBOARDING_STEPS.map((step) => {
          const isCurrent = location.pathname === step.route;
          const isDone = completed.includes(step.id);
          const isSkipped = skipped.includes(step.id);

          return (
            <li key={step.id}>
              <div
                className={cn(
                  'flex items-start gap-3 rounded-md px-3 py-2 text-sm transition-colors',
                  isCurrent
                    ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                    : 'text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800',
                )}
                aria-current={isCurrent ? 'step' : undefined}
                data-step={step.id}
              >
                <span className="mt-0.5 shrink-0" aria-hidden="true">
                  {isDone ? (
                    <Check className="h-4 w-4 text-emerald-500" />
                  ) : isSkipped ? (
                    <MinusCircle className="h-4 w-4 text-slate-400" />
                  ) : (
                    <Circle
                      className={cn(
                        'h-4 w-4',
                        isCurrent ? 'text-white dark:text-slate-900' : 'text-slate-400',
                      )}
                    />
                  )}
                </span>
                <span className="flex flex-col">
                  <span className="font-medium">{step.label}</span>
                  <span
                    className={cn(
                      'text-xs',
                      isCurrent
                        ? 'text-slate-200 dark:text-slate-700'
                        : 'text-slate-500 dark:text-slate-400',
                    )}
                  >
                    {step.description}
                  </span>
                </span>
              </div>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
// --- /L3.6 onboarding ---
