import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'jest-axe';
import { Button } from '@/components/ui/Button';

describe('Button', () => {
  it('renders children', () => {
    render(<Button>Save</Button>);
    expect(screen.getByRole('button', { name: 'Save' })).toBeInTheDocument();
  });

  it('defaults to type=button', () => {
    render(<Button>x</Button>);
    expect(screen.getByRole('button')).toHaveAttribute('type', 'button');
  });

  it('fires onClick', async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>x</Button>);
    await userEvent.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('disables and sets aria-busy when loading', () => {
    render(<Button loading>x</Button>);
    const btn = screen.getByRole('button');
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute('aria-busy', 'true');
  });

  it('does not fire onClick when disabled', async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick} disabled>x</Button>);
    await userEvent.click(screen.getByRole('button'));
    expect(onClick).not.toHaveBeenCalled();
  });

  it('has no a11y violations', async () => {
    const { container } = render(<Button>Submit</Button>);
    expect(await axe(container)).toHaveNoViolations();
  });
});
