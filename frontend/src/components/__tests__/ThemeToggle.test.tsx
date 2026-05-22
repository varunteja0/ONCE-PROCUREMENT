import { afterEach, describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ThemeToggle } from '@/components/ThemeToggle';

afterEach(() => {
  window.localStorage.clear();
  document.documentElement.classList.remove('dark');
});

describe('ThemeToggle', () => {
  it('renders 3 radio buttons', () => {
    render(<ThemeToggle />);
    expect(screen.getAllByRole('radio')).toHaveLength(3);
  });

  it('switches to dark theme on click', async () => {
    render(<ThemeToggle />);
    await userEvent.click(screen.getByRole('radio', { name: 'Dark theme' }));
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(window.localStorage.getItem('once.theme')).toBe('dark');
  });

  it('marks active radio with aria-checked=true', async () => {
    render(<ThemeToggle />);
    await userEvent.click(screen.getByRole('radio', { name: 'Light theme' }));
    expect(screen.getByRole('radio', { name: 'Light theme' })).toHaveAttribute(
      'aria-checked',
      'true',
    );
  });
});
