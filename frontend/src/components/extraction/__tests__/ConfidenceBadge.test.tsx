import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

import {
  ConfidenceBadge,
  tierFor,
} from '@/components/extraction/ConfidenceBadge';

describe('ConfidenceBadge', () => {
  it('renders green tier at 0.95', () => {
    render(<ConfidenceBadge value={0.95} />);
    const el = screen.getByTestId('confidence-badge');
    expect(el).toHaveAttribute('data-tier', 'green');
    expect(el).toHaveTextContent('95%');
  });

  it('renders yellow tier at 0.75', () => {
    render(<ConfidenceBadge value={0.75} />);
    expect(screen.getByTestId('confidence-badge')).toHaveAttribute(
      'data-tier',
      'yellow',
    );
  });

  it('renders red tier at 0.4', () => {
    render(<ConfidenceBadge value={0.4} />);
    expect(screen.getByTestId('confidence-badge')).toHaveAttribute(
      'data-tier',
      'red',
    );
  });

  it('clamps values above 1', () => {
    render(<ConfidenceBadge value={1.7} />);
    expect(screen.getByTestId('confidence-badge')).toHaveTextContent('100%');
  });

  it('clamps values below 0', () => {
    render(<ConfidenceBadge value={-0.5} />);
    expect(screen.getByTestId('confidence-badge')).toHaveTextContent('0%');
  });

  it('handles NaN safely', () => {
    render(<ConfidenceBadge value={Number.NaN} />);
    expect(screen.getByTestId('confidence-badge')).toHaveTextContent('0%');
  });

  it('honors a custom label', () => {
    render(<ConfidenceBadge value={0.95} label="auto" />);
    expect(screen.getByTestId('confidence-badge')).toHaveTextContent('auto');
  });

  it('exposes an accessible name', () => {
    render(<ConfidenceBadge value={0.95} />);
    expect(screen.getByRole('status')).toHaveAttribute(
      'aria-label',
      expect.stringContaining('95'),
    );
  });

  it('tierFor matches thresholds', () => {
    expect(tierFor(0.95)).toBe('green');
    expect(tierFor(0.9)).toBe('green');
    expect(tierFor(0.89)).toBe('yellow');
    expect(tierFor(0.6)).toBe('yellow');
    expect(tierFor(0.59)).toBe('red');
  });
});
