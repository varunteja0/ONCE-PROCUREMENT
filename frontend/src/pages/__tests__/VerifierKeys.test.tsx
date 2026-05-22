/**
 * @vitest-environment jsdom
 */
import { renderWithProviders } from '@/test/utils';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const useVerifierKeysMock = vi.fn();
const issueMutateAsync = vi.fn();
const revokeMutateAsync = vi.fn();

const issueMutation = {
  mutateAsync: issueMutateAsync,
  isPending: false,
  variables: undefined as string | undefined,
};
const revokeMutation = {
  mutateAsync: revokeMutateAsync,
  isPending: false,
  variables: undefined as string | undefined,
};

vi.mock('@/hooks/useVerifierKeys', () => ({
  useVerifierKeys: () => useVerifierKeysMock(),
  useIssueVerifierKey: () => issueMutation,
  useRevokeVerifierKey: () => revokeMutation,
}));

vi.mock('@/services/api', () => ({
  api: {},
  extractErrorMessage: (e: unknown, fb: string) =>
    e instanceof Error ? e.message : fb,
}));

vi.mock('@/lib/toast', () => ({
  default: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));

import VerifierKeys from '@/pages/VerifierKeys';

beforeEach(() => {
  useVerifierKeysMock.mockReset();
  issueMutateAsync.mockReset();
  revokeMutateAsync.mockReset();
});

function queryState<T>(
  data: T | undefined,
  status: 'success' | 'loading' | 'error' = 'success',
): {
  data: T | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
  refetch: () => void;
} {
  return {
    data,
    isLoading: status === 'loading',
    isError: status === 'error',
    error: status === 'error' ? new Error('boom') : null,
    refetch: vi.fn(),
  };
}

describe('VerifierKeys page', () => {
  it('shows empty state when no keys exist', () => {
    useVerifierKeysMock.mockReturnValue(queryState([]));
    renderWithProviders(<VerifierKeys />);
    expect(screen.getByText(/no verifier keys yet/i)).toBeInTheDocument();
  });

  it('lists existing keys with prefix and cap', () => {
    useVerifierKeysMock.mockReturnValue(
      queryState([
        {
          id: 'k1',
          tenant_id: 't1',
          name: 'ACME Carrier',
          key_prefix: 'vk_live_abc123',
          monthly_call_cap: 10000,
          last_used_at: null,
          created_at: '2026-05-01T00:00:00Z',
          revoked_at: null,
        },
      ]),
    );
    renderWithProviders(<VerifierKeys />);
    expect(screen.getByText(/acme carrier/i)).toBeInTheDocument();
    expect(screen.getByText(/vk_live_abc123/)).toBeInTheDocument();
    expect(screen.getByText(/10,000/)).toBeInTheDocument();
    expect(screen.getByText(/never/i)).toBeInTheDocument();
  });

  it('issues a key and shows plaintext exactly once', async () => {
    const user = userEvent.setup();
    useVerifierKeysMock.mockReturnValue(queryState([]));
    issueMutateAsync.mockResolvedValueOnce({
      id: 'k1',
      tenant_id: 't1',
      name: 'New Key',
      key_prefix: 'vk_live_xyz789',
      monthly_call_cap: 10000,
      last_used_at: null,
      created_at: '2026-05-01T00:00:00Z',
      revoked_at: null,
      plaintext: 'vk_live_xyz789-FULL-SECRET-VALUE',
    });

    renderWithProviders(<VerifierKeys />);
    expect(screen.getByText(/no verifier keys yet/i)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /issue key/i }));
    await user.type(screen.getByLabelText(/name/i), 'New Key');
    await user.click(
      screen.getAllByRole('button', { name: /issue key/i }).pop()!,
    );

    await waitFor(() =>
      expect(screen.getByTestId('vk-issued-modal')).toBeInTheDocument(),
    );
    expect(screen.getByTestId('vk-plaintext').textContent).toBe(
      'vk_live_xyz789-FULL-SECRET-VALUE',
    );
    expect(issueMutateAsync).toHaveBeenCalledWith({
      name: 'New Key',
      monthly_call_cap: null,
    });
  });

  it('parses cap=0 as uncapped (paid tier)', async () => {
    const user = userEvent.setup();
    useVerifierKeysMock.mockReturnValue(queryState([]));
    issueMutateAsync.mockResolvedValueOnce({
      id: 'k2',
      tenant_id: 't1',
      name: 'Paid Key',
      key_prefix: 'vk_live_paid000',
      monthly_call_cap: null,
      last_used_at: null,
      created_at: '2026-05-01T00:00:00Z',
      revoked_at: null,
      plaintext: 'vk_live_paid000-FULL',
    });

    renderWithProviders(<VerifierKeys />);
    await user.click(screen.getByRole('button', { name: /issue key/i }));
    await user.type(screen.getByLabelText(/name/i), 'Paid Key');
    await user.type(screen.getByLabelText(/monthly call cap/i), '0');
    await user.click(
      screen.getAllByRole('button', { name: /issue key/i }).pop()!,
    );

    await waitFor(() => expect(issueMutateAsync).toHaveBeenCalled());
    expect(issueMutateAsync).toHaveBeenCalledWith({
      name: 'Paid Key',
      monthly_call_cap: 0,
    });
  });

  it('revokes a key after confirmation', async () => {
    const user = userEvent.setup();
    useVerifierKeysMock.mockReturnValue(
      queryState([
        {
          id: 'k1',
          tenant_id: 't1',
          name: 'Doomed',
          key_prefix: 'vk_live_doom1234',
          monthly_call_cap: 10000,
          last_used_at: null,
          created_at: '2026-05-01T00:00:00Z',
          revoked_at: null,
        },
      ]),
    );
    revokeMutateAsync.mockResolvedValueOnce(undefined);

    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    renderWithProviders(<VerifierKeys />);

    await user.click(screen.getByRole('button', { name: /revoke/i }));
    expect(confirmSpy).toHaveBeenCalled();
    await waitFor(() => expect(revokeMutateAsync).toHaveBeenCalledWith('k1'));

    confirmSpy.mockRestore();
  });

  it('does not revoke when user cancels confirmation', async () => {
    const user = userEvent.setup();
    useVerifierKeysMock.mockReturnValue(
      queryState([
        {
          id: 'k1',
          tenant_id: 't1',
          name: 'Safe',
          key_prefix: 'vk_live_safe1234',
          monthly_call_cap: null,
          last_used_at: null,
          created_at: '2026-05-01T00:00:00Z',
          revoked_at: null,
        },
      ]),
    );
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    renderWithProviders(<VerifierKeys />);

    await user.click(screen.getByRole('button', { name: /revoke/i }));
    expect(revokeMutateAsync).not.toHaveBeenCalled();

    confirmSpy.mockRestore();
  });
});
