// --- L3.7 imports ---
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type * as ReactRouterDomModule from 'react-router-dom';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

const navigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof ReactRouterDomModule>(
    'react-router-dom',
  );
  return { ...actual, useNavigate: () => navigate };
});

const uploadMutateAsync = vi.fn();
const commitMutateAsync = vi.fn();

vi.mock('@/hooks/useImports', () => ({
  useImportColumns: () => ({
    data: {
      entity_type: 'supplier',
      columns: [
        {
          field: 'name',
          required: true,
          aliases: ['legal_name'],
          description: 'name',
          example: 'Acme',
        },
        {
          field: 'fein',
          required: true,
          aliases: ['ein'],
          description: 'fein',
          example: '12-3456789',
        },
        {
          field: 'state',
          required: true,
          aliases: [],
          description: 'state',
          example: 'CA',
        },
      ],
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useUploadImport: () => ({
    mutateAsync: uploadMutateAsync,
    isPending: false,
    error: null,
  }),
  useImport: (_id: string | undefined) => ({
    data: {
      id: 'job-123',
      tenant_id: 't1',
      entity_type: 'supplier',
      status: 'dry_run_ready',
      original_filename: 'suppliers.csv',
      file_size_bytes: 100,
      total_rows: 3,
      valid_rows: 2,
      invalid_rows: 1,
      imported_rows: 0,
      on_duplicate: 'error',
      mapping: { name: 'legal_name', fein: 'ein', state: 'state' },
      summary: null,
      last_error: null,
      created_by_user_id: null,
      created_at: '2024-01-01T00:00:00Z',
      started_at: null,
      completed_at: null,
      errors_preview: [
        {
          row_number: 3,
          column: 'fein',
          value: 'XX',
          error_code: 'invalid_format',
          error_message: 'Bad EIN',
        },
      ],
      error_count: 1,
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useCommitImport: () => ({
    mutateAsync: commitMutateAsync,
    isPending: false,
    error: null,
  }),
  useCancelImport: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
    error: null,
  }),
}));

import ImportNew from '@/pages/imports/ImportNew';

function renderPage(): void {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ImportNew />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('ImportNew page', () => {
  it('renders the three steps and entity selector', () => {
    renderPage();
    expect(screen.getByRole('heading', { name: /New Bulk Import/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/Entity/i)).toBeInTheDocument();
    expect(screen.getByText(/1 · Choose what to import/i)).toBeInTheDocument();
  });

  it('moves to mapping after a file is dropped, then uploads & shows commit button', async () => {
    uploadMutateAsync.mockResolvedValueOnce({
      id: 'job-123',
      tenant_id: 't1',
      entity_type: 'supplier',
      status: 'dry_run_ready',
      original_filename: 'suppliers.csv',
      file_size_bytes: 100,
      total_rows: 3,
      valid_rows: 2,
      invalid_rows: 1,
      imported_rows: 0,
      on_duplicate: 'error',
      mapping: {},
      summary: null,
      last_error: null,
      created_by_user_id: null,
      created_at: '2024-01-01T00:00:00Z',
      started_at: null,
      completed_at: null,
    });
    renderPage();
    const input = document.querySelector('input[type=file]') as HTMLInputElement;
    const file = new File(
      ['legal_name,ein,state\nAcme,12-3456789,CA\n'],
      'suppliers.csv',
      { type: 'text/csv' },
    );
    await userEvent.upload(input, file);
    expect(await screen.findByText(/2 · Map columns/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /^Validate$/ }));
    await waitFor(() => expect(uploadMutateAsync).toHaveBeenCalled());

    // Step 3 shows commit with valid_rows
    expect(await screen.findByRole('button', { name: /Commit 2 rows/i })).toBeInTheDocument();
  });

  it('commit button calls commitMutateAsync and navigates', async () => {
    uploadMutateAsync.mockResolvedValueOnce({
      id: 'job-123',
      status: 'dry_run_ready',
      total_rows: 3,
      valid_rows: 2,
      invalid_rows: 1,
      imported_rows: 0,
    });
    commitMutateAsync.mockResolvedValueOnce({ id: 'job-123', status: 'importing' });

    renderPage();
    const input = document.querySelector('input[type=file]') as HTMLInputElement;
    await userEvent.upload(
      input,
      new File(['legal_name,ein,state\nA,12-3456789,CA\n'], 's.csv', { type: 'text/csv' }),
    );
    await userEvent.click(screen.getByRole('button', { name: /^Validate$/ }));
    const commitBtn = await screen.findByRole('button', { name: /Commit 2 rows/i });
    await userEvent.click(commitBtn);
    await waitFor(() => expect(commitMutateAsync).toHaveBeenCalledWith('job-123'));
    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/imports/job-123'));
  });
});
// --- /L3.7 imports ---
