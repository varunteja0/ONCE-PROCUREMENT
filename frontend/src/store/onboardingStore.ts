// --- L3.6 onboarding ---
import { create } from 'zustand';
import type { OnboardingStateRead, OnboardingStep } from '@/services/onboardingApi';

export const ONBOARDING_STEPS: ReadonlyArray<{
  id: OnboardingStep;
  label: string;
  description: string;
  route: string;
}> = [
  { id: 'start', label: 'Sign up', description: 'Create your account', route: '/onboarding/signup' },
  { id: 'email_verify', label: 'Verify email', description: 'Confirm it’s you', route: '/onboarding/verify-email' },
  { id: 'profile', label: 'Company profile', description: 'Tell us about the MGA', route: '/onboarding/profile' },
  { id: 'plan', label: 'Choose a plan', description: 'Pick free or paid', route: '/onboarding/plan' },
  { id: 'portal', label: 'Connect a portal', description: 'Optional — link a carrier portal', route: '/onboarding/portal' },
  { id: 'supplier', label: 'Add a supplier', description: 'Record the first agency you submit for', route: '/onboarding/supplier' },
  { id: 'submission', label: 'First submission', description: 'Queue a dry-run submission', route: '/onboarding/submission' },
  { id: 'done', label: 'You’re live', description: 'Welcome to Once', route: '/onboarding/done' },
] as const;

export interface OnboardingDraft {
  email?: string;
  companyName?: string;
  tenantId?: string;
  devVerificationCode?: string | null;
  pendingSubmissionId?: string;
  [k: string]: unknown;
}

interface OnboardingStoreState {
  currentStep: OnboardingStep;
  completedSteps: OnboardingStep[];
  skippedSteps: OnboardingStep[];
  draft: OnboardingDraft;
  setStep: (s: OnboardingStep) => void;
  setDraft: (patch: Partial<OnboardingDraft>) => void;
  hydrate: (state: OnboardingStateRead) => void;
  reset: () => void;
}

export const useOnboardingStore = create<OnboardingStoreState>((set) => ({
  currentStep: 'start',
  completedSteps: [],
  skippedSteps: [],
  draft: {},
  setStep: (s) => set({ currentStep: s }),
  setDraft: (patch) => set((prev) => ({ draft: { ...prev.draft, ...patch } })),
  hydrate: (state) =>
    set({
      currentStep: state.current_step,
      completedSteps: Object.keys(state.completed_steps ?? {}) as OnboardingStep[],
      skippedSteps: Object.keys(state.skipped_steps ?? {}) as OnboardingStep[],
    }),
  reset: () => set({ currentStep: 'start', completedSteps: [], skippedSteps: [], draft: {} }),
}));
// --- /L3.6 onboarding ---
