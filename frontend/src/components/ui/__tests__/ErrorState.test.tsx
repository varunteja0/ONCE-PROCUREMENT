import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ErrorState } from '@/components/ui/ErrorState';

describe('ErrorState', () => {
  it('renders default title and Please try again', () => {
    render(<ErrorState />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });
  it('renders custom description', () => {
    render(<ErrorState description="boom" />);
    expect(screen.getByText('boom')).toBeInTheDocument();
  });
  it('renders retry button and calls onRetry', async () => {
    const onRetry = vi.fn();
    render(<ErrorState onRetry={onRetry} />);
    await userEvent.click(screen.getByRole('button', { name: /retry/i }));
    expect(onRetry).toHaveBeenCalled();
  });
});
