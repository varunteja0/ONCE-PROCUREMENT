import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PaginationControls } from '@/components/ui/PaginationControls';

describe('PaginationControls', () => {
  it('disables Prev on page 1', () => {
    render(<PaginationControls page={1} pageSize={10} total={50} onPageChange={() => {}} />);
    expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Next page' })).not.toBeDisabled();
  });

  it('disables Next on last page', () => {
    render(<PaginationControls page={5} pageSize={10} total={50} onPageChange={() => {}} />);
    expect(screen.getByRole('button', { name: 'Next page' })).toBeDisabled();
  });

  it('calls onPageChange when Next clicked', async () => {
    const onPageChange = vi.fn();
    render(<PaginationControls page={1} pageSize={10} total={50} onPageChange={onPageChange} />);
    await userEvent.click(screen.getByRole('button', { name: 'Next page' }));
    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  it('renders "No results" when total is 0', () => {
    render(<PaginationControls page={1} pageSize={10} total={0} onPageChange={() => {}} />);
    expect(screen.getByText('No results')).toBeInTheDocument();
  });
});
