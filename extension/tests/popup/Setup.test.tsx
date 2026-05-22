/**
 * Tests for popup/screens/Setup — email + password login flow.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const setApiBase = vi.fn<(base: string) => Promise<void>>();
vi.mock("../../src/lib/storage", async () => {
  const actual = await vi.importActual<Record<string, unknown>>(
    "../../src/lib/storage",
  );
  return {
    ...actual,
    setApiBase: (b: string) => setApiBase(b),
  };
});

const send = vi.fn<(msg: { type: string; passphrase?: string }) => Promise<{ ok: true; unlocked: boolean }>>();
vi.mock("../../src/lib/messaging", () => ({
  send: (msg: { type: string; passphrase?: string }) => send(msg),
}));

const login = vi.fn<(email: string, password: string) => Promise<{ access_token: string; refresh_token: string; token_type: string }>>();
vi.mock("../../src/lib/api", () => ({
  login: (e: string, p: string) => login(e, p),
}));

const vaultInit = vi.fn<(p: string) => Promise<void>>();
const vaultIsInitialized = vi.fn<() => Promise<boolean>>();
vi.mock("../../src/lib/vault", () => ({
  init: (p: string) => vaultInit(p),
  isInitialized: () => vaultIsInitialized(),
}));

import { Setup } from "../../src/popup/screens/Setup";

beforeEach(() => {
  setApiBase.mockReset();
  send.mockReset();
  login.mockReset();
  vaultInit.mockReset();
  vaultIsInitialized.mockReset();
  setApiBase.mockResolvedValue(undefined);
  send.mockResolvedValue({ ok: true, unlocked: true });
  login.mockResolvedValue({
    access_token: "a",
    refresh_token: "r",
    token_type: "bearer",
  });
  vaultInit.mockResolvedValue(undefined);
  vaultIsInitialized.mockResolvedValue(false);
});

describe("Setup screen", () => {
  it("signs in, initialises the vault, unlocks, and calls onDone", async () => {
    const onDone = vi.fn();
    render(<Setup onDone={onDone} />);

    fireEvent.change(screen.getByLabelText(/Email/i), {
      target: { value: "alice@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/^Password$/i), {
      target: { value: "hunter2hunter2" },
    });
    fireEvent.change(screen.getByLabelText(/^Vault passphrase$/i), {
      target: { value: "correct horse" },
    });
    fireEvent.change(screen.getByLabelText(/Confirm passphrase/i), {
      target: { value: "correct horse" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Sign in/i }));

    await waitFor(() => {
      expect(onDone).toHaveBeenCalledTimes(1);
    });

    expect(setApiBase).toHaveBeenCalledWith("http://localhost:8000");
    expect(login).toHaveBeenCalledWith("alice@example.com", "hunter2hunter2");
    expect(vaultInit).toHaveBeenCalledWith("correct horse");
    expect(send).toHaveBeenCalledWith({
      type: "vault.unlock",
      passphrase: "correct horse",
    });
  });

  it("rejects mismatched passphrases without calling login", async () => {
    render(<Setup onDone={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/Email/i), {
      target: { value: "alice@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/^Password$/i), {
      target: { value: "hunter2hunter2" },
    });
    fireEvent.change(screen.getByLabelText(/^Vault passphrase$/i), {
      target: { value: "abcdefgh" },
    });
    fireEvent.change(screen.getByLabelText(/Confirm passphrase/i), {
      target: { value: "different" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Sign in/i }));

    await waitFor(() => {
      expect(screen.getByText(/do not match/i)).toBeInTheDocument();
    });
    expect(login).not.toHaveBeenCalled();
  });
});
