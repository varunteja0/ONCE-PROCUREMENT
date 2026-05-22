// --- L3.6 onboarding ---
import { useEffect } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { ONBOARDING_STEPS } from '@/store/onboardingStore';
import { useOnboardingState } from '@/hooks/useOnboarding';
import { onboardingTokenStorage } from '@/services/onboardingApi';
import { tokenStorage } from '@/services/api';

/**
 * Wizard entry. Hydrates server state and forwards to the right step.
 * If the user has no onboarding session at all → /onboarding/signup.
 */
export default function Wizard(): JSX.Element {
  const hasAccess = tokenStorage.getAccess() !== null;
  const hasOnboardingToken = onboardingTokenStorage.get() !== null;
  const { data, isLoading } = useOnboardingState(hasAccess);
  const navigate = useNavigate();

  useEffect(() => {
    if (!data) return;
    const target = ONBOARDING_STEPS.find((s) => s.id === data.current_step);
    if (target) navigate(target.route, { replace: true });
  }, [data, navigate]);

  if (!hasAccess && !hasOnboardingToken) {
    return <Navigate to="/onboarding/signup" replace />;
  }
  if (!hasAccess && hasOnboardingToken) {
    return <Navigate to="/onboarding/verify-email" replace />;
  }
  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-slate-500">
        Loading your wizard…
      </div>
    );
  }
  return <Navigate to="/onboarding/signup" replace />;
}
// --- /L3.6 onboarding ---
