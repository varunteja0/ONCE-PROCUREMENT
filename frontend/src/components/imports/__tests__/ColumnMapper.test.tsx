// --- L3.7 imports ---
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import {
  ColumnMapper,
  suggestMapping,
} from '@/components/imports/ColumnMapper';
import type { ImportColumnSpec } from '@/services/importsApi';

const COLS: ImportColumnSpec[] = [
  {
    field: 'name',
    required: true,
    aliases: ['company', 'legal_name'],
    description: 'Supplier name',
    example: 'Acme',
  },
  {
    field: 'fein',
    required: true,
    aliases: ['ein', 'tax_id'],
    description: 'EIN',
    example: '12-3456789',
  },
  {
    field: 'email',
    required: false,
    aliases: ['primary_email'],
    description: 'Email',
    example: 'a@b',
  },
];

describe('suggestMapping', () => {
  it('matches by exact field name (case + separator insensitive)', () => {
    const m = suggestMapping(COLS, ['Legal Name', 'Tax_ID', 'Primary Email']);
    expect(m).toEqual({
      name: 'Legal Name',
      fein: 'Tax_ID',
      email: 'Primary Email',
    });
  });
  it('leaves unmatched fields undefined', () => {
    const m = suggestMapping(COLS, ['random', 'whatever']);
    expect(m).toEqual({});
  });
});

describe('ColumnMapper', () => {
  it('shows a warning when required fields are unmapped', () => {
    render(
      <ColumnMapper
        fileHeaders={['foo', 'bar']}
        schemaColumns={COLS}
        value={{}}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByRole('alert').textContent).toMatch(/Map required columns/i);
    expect(screen.getByRole('alert').textContent).toMatch(/name/);
    expect(screen.getByRole('alert').textContent).toMatch(/fein/);
  });

  it('emits onChange when a select changes', () => {
    const onChange = vi.fn();
    render(
      <ColumnMapper
        fileHeaders={['Legal Name', 'EIN']}
        schemaColumns={COLS}
        value={{}}
        onChange={onChange}
      />,
    );
    const sel = screen.getByLabelText(/Source header for name/i);
    fireEvent.change(sel, { target: { value: 'Legal Name' } });
    expect(onChange).toHaveBeenCalledWith({ name: 'Legal Name' });
  });

  it('removes a field on unmapping back to placeholder', () => {
    const onChange = vi.fn();
    render(
      <ColumnMapper
        fileHeaders={['Legal Name']}
        schemaColumns={COLS}
        value={{ name: 'Legal Name' }}
        onChange={onChange}
      />,
    );
    const sel = screen.getByLabelText(/Source header for name/i);
    fireEvent.change(sel, { target: { value: '__unmapped__' } });
    expect(onChange).toHaveBeenCalledWith({});
  });
});
// --- /L3.7 imports ---
