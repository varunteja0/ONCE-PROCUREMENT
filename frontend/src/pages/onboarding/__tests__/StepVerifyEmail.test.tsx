import StepVerifyEmail from '@/pages/onboarding/StepVerifyEmail';
import type * as OnboardingApiModule from '@/services/onboardingApi';
import { useOnboardingStore } from '@/store/onboardingStore';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const verifyEmailMock = vi.fn();
vi.mock('@/services/onboardingApi', async () => {
  const actual = await vi.importActual<typeof OnboardingApiModule>(
    '@/services/onboardingApi',
  );
  return {
    ...actual,
    onboarding: {
      ...actual.onboarding,
      verifyEmail: (...args: unknown[]) => verifyEmailMock(...args),
    },
    onboardingTokenStorage: { clear: vi.fn(), get: () => 'tok', set: vi.fn() },
  };
});

vi.mock('@/services/api', () => ({
  tokenStorage: { setPair: vi.fn() },
}));

vi.mock('@/lib/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

function setup(): void {
  render(
    <MemoryRouter initialEntries={['/onboarding/verify-email']}>
      <StepVerifyEmail />
    </MemoryRouter>,
  );
}

describe('StepVerifyEmail', () => {
  beforeEach(() => {
    verifyEmailMock.mockReset();
    useOnboardingStore.setState({
      draft: { email: 'founder@example.com', devVerificationCode: null },
    });
  });

  it('rejects non-6-digit codes', async () => {
    setup();
    await userEvent.type(screen.getByLabelText(/verification code/i), '12');
    await userEvent.click(screen.getByRole('button', { name: /verify/i }));
    expect(verifyEmailMock).not.toHaveBeenCalled();
    expect(await screen.findByRole('alert')).toHaveTextContent(/6-digit/i);
  });

  it('calls verifyEmail with a 6-digit code', async () => {
    verifyEmailMock.mockResolvedValue({
      access_token: 'a',
      refresh_token: 'r',
      token_type: 'bearer',
      tenant_id: 't',
      current_step: 'profile',
    });
    setup();
    await userEvent.type(screen.getByLabelText(/verification code/i), '123456');
    await userEvent.click(screen.getByRole('button', { name: /verify/i }));
    expect(verifyEmailMock).toHaveBeenCalledWith('123456');
  });
});
