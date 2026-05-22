import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ProgressRail from '@/components/onboarding/ProgressRail';
import { useOnboardingStore } from '@/store/onboardingStore';

function renderAt(path: string): ReturnType<typeof render> {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ProgressRail />
    </MemoryRouter>,
  );
}

describe('ProgressRail', () => {
  it('marks the current route with aria-current=step', () => {
    useOnboardingStore.setState({ completedSteps: [], skippedSteps: [] });
    renderAt('/onboarding/profile');
    const current = document.querySelector('[aria-current="step"]');
    expect(current).not.toBeNull();
    expect(current?.getAttribute('data-step')).toBe('profile');
  });

  it('renders all 8 wizard steps', () => {
    useOnboardingStore.setState({ completedSteps: [], skippedSteps: [] });
    renderAt('/onboarding/signup');
    expect(screen.getAllByRole('listitem')).toHaveLength(8);
  });

  it('shows completed steps with a check', () => {
    useOnboardingStore.setState({ completedSteps: ['start', 'email_verify'], skippedSteps: [] });
    const { container } = renderAt('/onboarding/profile');
    // Check icons are rendered via lucide-react svg; assert at least 2 exist.
    const svgs = container.querySelectorAll('svg.lucide-check');
    expect(svgs.length).toBeGreaterThanOrEqual(2);
  });
});
