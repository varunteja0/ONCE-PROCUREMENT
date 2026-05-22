import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'jest-axe';
import { Input } from '@/components/ui/Input';

describe('Input', () => {
  it('renders label and associates it with the input', () => {
    render(<Input label="Email" />);
    const input = screen.getByLabelText('Email');
    expect(input).toBeInTheDocument();
  });

  it('shows error message and sets aria-invalid', () => {
    render(<Input label="Email" error="Required" />);
    expect(screen.getByRole('alert')).toHaveTextContent('Required');
    expect(screen.getByLabelText('Email')).toHaveAttribute('aria-invalid', 'true');
  });

  it('shows hint when no error', () => {
    render(<Input label="Email" hint="we never share it" />);
    expect(screen.getByText('we never share it')).toBeInTheDocument();
  });

  it('accepts user input', async () => {
    render(<Input label="Name" />);
    const el = screen.getByLabelText('Name');
    await userEvent.type(el, 'jane');
    expect(el).toHaveValue('jane');
  });

  it('has no a11y violations', async () => {
    const { container } = render(<Input label="Email" hint="hi" />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
