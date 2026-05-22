import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'jest-axe';
import { EmptyState } from '@/components/ui/EmptyState';

describe('EmptyState', () => {
  it('renders title and description', () => {
    render(<EmptyState title="No data" description="Try adjusting filters" />);
    expect(screen.getByText('No data')).toBeInTheDocument();
    expect(screen.getByText('Try adjusting filters')).toBeInTheDocument();
  });

  it('renders action and fires onClick', async () => {
    const onClick = vi.fn();
    render(<EmptyState title="No data" action={{ label: 'Add', onClick }} />);
    await userEvent.click(screen.getByRole('button', { name: 'Add' }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('has no a11y violations', async () => {
    const { container } = render(<EmptyState title="No data" />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
