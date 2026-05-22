// --- L3.6 onboarding ---
import { useCallback, useEffect, useState } from 'react';
import {
  onboarding,
  onboardingTokenStorage,
  type OnboardingStateRead,
} from '@/services/onboardingApi';
import { useOnboardingStore } from '@/store/onboardingStore';

export function useOnboardingState(enabled = true): {
  data: OnboardingStateRead | null;
  isLoading: boolean;
  refetch: () => Promise<OnboardingStateRead | null>;
  error: unknown;
} {
  const hydrate = useOnboardingStore((s) => s.hydrate);
  const [data, setData] = useState<OnboardingStateRead | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(enabled);
  const [error, setError] = useState<unknown>(null);

  const refetch = useCallback(async (): Promise<OnboardingStateRead | null> => {
    setIsLoading(true);
    try {
      const s = await onboarding.state();
      setData(s);
      hydrate(s);
      setError(null);
      return s;
    } catch (e) {
      setError(e);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [hydrate]);

  useEffect(() => {
    if (!enabled) return;
    void refetch();
  }, [enabled, refetch]);

  return { data, isLoading, refetch, error };
}

export function clearOnboardingSession(): void {
  onboardingTokenStorage.clear();
  useOnboardingStore.getState().reset();
}
// --- /L3.6 onboarding ---
