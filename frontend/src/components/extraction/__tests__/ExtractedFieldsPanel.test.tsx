import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';

import { ExtractedFieldsPanel } from '@/components/extraction/ExtractedFieldsPanel';
import type { ExtractionRead } from '@/services/extractionsApi';

function baseExtraction(overrides: Partial<ExtractionRead> = {}): ExtractionRead {
  return {
    id: 'ext-1',
    tenant_id: 't-1',
    source_document_type: 'coi',
    source_document_id: 'doc-1',
    raw_text_url: null,
    extracted_fields: {
      policy_number: 'GL-2026-00001',
      effective_date: '2026-01-15',
      limit_each_occurrence_cents: 100_000_000,
      additional_insured: true,
      policies: [{ coverage_type: 'commercial_general_liability' }],
    },
    field_confidences: {
      policy_number: 0.95,
      effective_date: 0.8,
      limit_each_occurrence_cents: 0.5,
    },
    warnings: ['effective_date and expiry_date are inverted'],
    extractor_version: 'coi-1.0.0',
    status: 'succeeded',
    error: null,
    reviewed_by_user_id: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

describe('ExtractedFieldsPanel', () => {
  it('renders one row per extracted field', () => {
    render(<ExtractedFieldsPanel extraction={baseExtraction()} />);
    expect(screen.getByText('Policy Number')).toBeInTheDocument();
    expect(screen.getByText('Effective Date')).toBeInTheDocument();
  });

  it('renders status and warnings', () => {
    render(<ExtractedFieldsPanel extraction={baseExtraction()} />);
    expect(screen.getByTestId('status')).toHaveTextContent('succeeded');
    expect(screen.getByTestId('warnings')).toHaveTextContent('inverted');
  });

  it('shows confidence badges where confidences are present', () => {
    render(<ExtractedFieldsPanel extraction={baseExtraction()} />);
    expect(screen.getAllByTestId('confidence-badge').length).toBeGreaterThanOrEqual(3);
  });

  it('renders nested values as JSON without an override input', () => {
    render(<ExtractedFieldsPanel extraction={baseExtraction()} />);
    expect(screen.getByText(/commercial_general_liability/)).toBeInTheDocument();
    expect(screen.queryByTestId('override-policies')).toBeNull();
  });

  it('invokes onAccept with overridden values, preserving numeric types', () => {
    const onAccept = vi.fn();
    render(
      <ExtractedFieldsPanel extraction={baseExtraction()} onAccept={onAccept} />,
    );
    fireEvent.change(screen.getByTestId('override-policy_number'), {
      target: { value: 'GL-MANUAL-001' },
    });
    fireEvent.change(screen.getByTestId('override-limit_each_occurrence_cents'), {
      target: { value: '250000000' },
    });
    fireEvent.click(screen.getByTestId('accept-button'));
    expect(onAccept).toHaveBeenCalledTimes(1);
    const passed = onAccept.mock.calls[0][0];
    expect(passed.policy_number).toBe('GL-MANUAL-001');
    expect(passed.limit_each_occurrence_cents).toBe(250_000_000);
  });

  it('invokes onReject with the entered reason', () => {
    const onReject = vi.fn();
    render(
      <ExtractedFieldsPanel extraction={baseExtraction()} onReject={onReject} />,
    );
    fireEvent.change(screen.getByTestId('reject-reason'), {
      target: { value: 'wrong document' },
    });
    fireEvent.click(screen.getByTestId('reject-button'));
    expect(onReject).toHaveBeenCalledWith('wrong document');
  });

  it('omits accept/reject buttons in read-only mode', () => {
    render(
      <ExtractedFieldsPanel
        extraction={baseExtraction({ status: 'accepted' })}
        readOnly
      />,
    );
    expect(screen.queryByTestId('accept-button')).toBeNull();
    expect(screen.queryByTestId('reject-button')).toBeNull();
  });

  it('handles the empty-fields case', () => {
    render(
      <ExtractedFieldsPanel
        extraction={baseExtraction({
          extracted_fields: {},
          field_confidences: {},
          warnings: [],
        })}
      />,
    );
    expect(screen.getByText('No fields extracted.')).toBeInTheDocument();
  });
});
