// --- L3.9 inbound ---
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RoutingResultBadge } from '../RoutingResultBadge';

describe('RoutingResultBadge', () => {
  it('renders friendly label for each status', () => {
    render(<RoutingResultBadge status="routed" />);
    expect(screen.getByText('Routed')).toBeInTheDocument();
  });

  it('shows quarantined label', () => {
    render(<RoutingResultBadge status="quarantined" />);
    expect(screen.getByText('Quarantined')).toBeInTheDocument();
  });

  it('shows routing_failed as "Routing failed"', () => {
    render(<RoutingResultBadge status="routing_failed" />);
    expect(screen.getByText('Routing failed')).toBeInTheDocument();
  });
});
