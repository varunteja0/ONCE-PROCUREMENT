import { describe, expect, it, vi } from 'vitest';
import { useState } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'jest-axe';
import { MultiSelect } from '@/components/ui/MultiSelect';

function Harness({ onChange }: { onChange?: (v: string[]) => void }): JSX.Element {
  const [v, setV] = useState<string[]>([]);
  return (
    <MultiSelect
      label="Portals"
      options={[
        { value: 'a', label: 'Portal A' },
        { value: 'b', label: 'Portal B' },
      ]}
      value={v}
      onChange={(next) => {
        setV(next);
        onChange?.(next);
      }}
    />
  );
}

describe('MultiSelect', () => {
  it('toggles selection on click', async () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    await userEvent.click(screen.getByText('Portal A'));
    expect(onChange).toHaveBeenLastCalledWith(['a']);
    await userEvent.click(screen.getByText('Portal B'));
    expect(onChange).toHaveBeenLastCalledWith(['a', 'b']);
    await userEvent.click(screen.getByText('Portal A'));
    expect(onChange).toHaveBeenLastCalledWith(['b']);
  });

  it('renders error message', () => {
    render(
      <MultiSelect
        label="x"
        options={[{ value: 'a', label: 'A' }]}
        value={[]}
        onChange={() => {}}
        error="pick one"
      />,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('pick one');
  });

  it('has no a11y violations', async () => {
    const { container } = render(<Harness />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
