import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StatusBadge } from '@/components/ui/StatusBadge';

describe('StatusBadge', () => {
  it('renders Completed label', () => {
    render(<StatusBadge status="completed" />);
    expect(screen.getByText('Completed')).toBeInTheDocument();
  });
  it('renders Failed label', () => {
    render(<StatusBadge status="failed" />);
    expect(screen.getByText('Failed')).toBeInTheDocument();
  });
  it('sets data-status attribute', () => {
    render(<StatusBadge status="queued" />);
    expect(screen.getByText('Queued')).toHaveAttribute('data-status', 'queued');
  });
  it('exposes accessible name', () => {
    render(<StatusBadge status="running" />);
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Status: Running');
  });
});
