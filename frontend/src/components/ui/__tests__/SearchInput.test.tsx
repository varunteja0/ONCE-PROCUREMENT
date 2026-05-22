import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SearchInput } from '@/components/ui/SearchInput';

describe('SearchInput', () => {
  it('calls onChange with typed value', async () => {
    const onChange = vi.fn();
    render(<SearchInput value="" onChange={onChange} placeholder="Find" />);
    await userEvent.type(screen.getByPlaceholderText('Find'), 'a');
    expect(onChange).toHaveBeenCalledWith('a');
  });
  it('shows clear button when value present, clears on click', async () => {
    const onChange = vi.fn();
    render(<SearchInput value="hello" onChange={onChange} />);
    await userEvent.click(screen.getByRole('button', { name: 'Clear search' }));
    expect(onChange).toHaveBeenCalledWith('');
  });
  it('does not show clear when empty', () => {
    render(<SearchInput value="" onChange={() => {}} />);
    expect(screen.queryByRole('button', { name: 'Clear search' })).toBeNull();
  });
});
