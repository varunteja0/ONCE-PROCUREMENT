import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Select } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';
import { Skeleton, SkeletonText, SkeletonTable } from '@/components/ui/Skeleton';

describe('Select', () => {
  it('renders options and placeholder', () => {
    render(
      <Select
        label="Country"
        placeholder="Pick one"
        options={[
          { value: 'us', label: 'USA' },
          { value: 'ca', label: 'Canada' },
        ]}
      />,
    );
    expect(screen.getByLabelText('Country')).toBeInTheDocument();
    expect(screen.getByText('USA')).toBeInTheDocument();
    expect(screen.getByText('Pick one')).toBeInTheDocument();
  });
  it('shows error', () => {
    render(<Select label="x" options={[]} error="bad" />);
    expect(screen.getByRole('alert')).toHaveTextContent('bad');
  });
});

describe('Textarea', () => {
  it('renders label and accepts rows', () => {
    render(<Textarea label="Notes" rows={6} />);
    const t = screen.getByLabelText('Notes') as HTMLTextAreaElement;
    expect(t.rows).toBe(6);
  });
  it('shows error', () => {
    render(<Textarea label="x" error="too long" />);
    expect(screen.getByRole('alert')).toHaveTextContent('too long');
  });
});

describe('Skeleton', () => {
  it('renders status role', () => {
    render(<Skeleton aria-label="loading" />);
    expect(screen.getByRole('status', { name: 'loading' })).toBeInTheDocument();
  });
  it('SkeletonText renders n lines', () => {
    const { container } = render(<SkeletonText lines={4} />);
    expect(container.querySelectorAll('[aria-busy="true"]').length).toBeGreaterThan(0);
  });
  it('SkeletonTable renders', () => {
    render(<SkeletonTable rows={2} columns={3} />);
    expect(screen.getByRole('status', { name: 'Loading table' })).toBeInTheDocument();
  });
});
