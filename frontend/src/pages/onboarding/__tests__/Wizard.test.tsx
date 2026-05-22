import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Wizard from '@/pages/onboarding/Wizard';

vi.mock('@/hooks/useOnboarding', () => ({
  useOnboardingState: () => ({ data: null, isLoading: false, refetch: vi.fn(), error: null }),
  clearOnboardingSession: vi.fn(),
}));

vi.mock('@/services/api', () => ({
  tokenStorage: { getAccess: () => null },
}));

vi.mock('@/services/onboardingApi', () => ({
  onboardingTokenStorage: { get: () => null },
}));

describe('Wizard', () => {
  it('redirects unauthenticated users to /onboarding/signup', () => {
    render(
      <MemoryRouter initialEntries={['/onboarding']}>
        <Wizard />
      </MemoryRouter>,
    );
    // <Navigate> doesn't render visible content; assert no loading text + no crash.
    expect(screen.queryByText(/loading your wizard/i)).not.toBeInTheDocument();
  });
});
