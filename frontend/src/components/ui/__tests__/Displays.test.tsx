import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MoneyDisplay } from '@/components/ui/MoneyDisplay';
import { DateDisplay } from '@/components/ui/DateDisplay';

describe('MoneyDisplay', () => {
  it('renders fallback for null', () => {
    render(<MoneyDisplay value={null} />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });
  it('renders formatted value', () => {
    render(<MoneyDisplay value={1234} />);
    expect(screen.getByText(/1,234/)).toBeInTheDocument();
  });
});

describe('DateDisplay', () => {
  it('renders fallback for null', () => {
    render(<DateDisplay value={null} />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });
  it('uses <time> with dateTime attribute when value present', () => {
    const iso = '2024-06-15T12:00:00Z';
    const { container } = render(<DateDisplay value={iso} mode="date" />);
    const t = container.querySelector('time');
    expect(t).not.toBeNull();
    expect(t!.getAttribute('datetime')).toBe(iso);
  });
});
