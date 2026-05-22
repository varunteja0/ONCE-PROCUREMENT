import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ErrorBoundary } from '@/components/ErrorBoundary';

function Bomb({ explode }: { explode: boolean }): JSX.Element {
  if (explode) throw new Error('kaboom');
  return <div>safe</div>;
}

describe('ErrorBoundary', () => {
  it('renders children when no error', () => {
    render(
      <ErrorBoundary>
        <Bomb explode={false} />
      </ErrorBoundary>,
    );
    expect(screen.getByText('safe')).toBeInTheDocument();
  });

  it('renders fallback UI when child throws', () => {
    const err = vi.spyOn(console, 'error').mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <Bomb explode />
      </ErrorBoundary>,
    );
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('This view crashed')).toBeInTheDocument();
    err.mockRestore();
  });

  it('calls onError when child throws', () => {
    const err = vi.spyOn(console, 'error').mockImplementation(() => {});
    const onError = vi.fn();
    render(
      <ErrorBoundary onError={onError}>
        <Bomb explode />
      </ErrorBoundary>,
    );
    expect(onError).toHaveBeenCalled();
    err.mockRestore();
  });

  it('uses custom fallback when provided', async () => {
    const err = vi.spyOn(console, 'error').mockImplementation(() => {});
    render(
      <ErrorBoundary
        fallback={(e, reset) => (
          <button onClick={reset}>retry: {e.message}</button>
        )}
      >
        <Bomb explode />
      </ErrorBoundary>,
    );
    const btn = screen.getByRole('button', { name: /retry: kaboom/ });
    expect(btn).toBeInTheDocument();
    await userEvent.click(btn);
    err.mockRestore();
  });
});
