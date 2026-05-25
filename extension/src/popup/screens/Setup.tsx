import { Loader2, ShieldCheck } from "lucide-react";
import type { FormEvent } from "react";
import { useState } from "react";

import { login } from "../../lib/api";
import { send } from "../../lib/messaging";
import { setApiBase } from "../../lib/storage";
import { init as vaultInit, isInitialized as vaultIsInitialized } from "../../lib/vault";

interface Props {
  onDone: () => void | Promise<void>;
}

/**
 * First-run Setup. Two concerns combined to minimise round-trips:
 *  1. Sign in to the backend with email + password (background persists
 *     the access + refresh tokens via the SAVE_TOKENS contract embedded
 *     in `lib/api.login`).
 *  2. Choose a vault passphrase (creates an encrypted vault).
 *
 * The previous flow asked the user to paste an access token by hand,
 * which both leaked tokens via the clipboard and left no refresh token
 * for silent re-auth. The login flow fixes both.
 */
export function Setup({ onDone }: Props): JSX.Element {
  const [apiBase, setApiBaseInput] = useState("http://localhost:8000");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passphrase, setPassphrase] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async (e: FormEvent): Promise<void> => {
    e.preventDefault();
    setError(null);

    if (passphrase.length < 8) {
      setError("Passphrase must be at least 8 characters.");
      return;
    }
    if (passphrase !== confirm) {
      setError("Passphrases do not match.");
      return;
    }
    if (!email.trim() || !password) {
      setError("Email and password are required.");
      return;
    }
    setBusy(true);
    try {
      // Persist API base first so the background's `api.call` proxy uses
      // the right origin for the login round-trip.
      await setApiBase(apiBase.trim());

      // `login` performs the POST and asks the background to persist the
      // refresh token alongside the access token (SAVE_TOKENS contract).
      await login(email.trim(), password);

      const already = await vaultIsInitialized();
      if (!already) {
        await vaultInit(passphrase);
      }
      await send({ type: "vault.unlock" });
      await onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "setup_failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="flex-1 overflow-y-auto" aria-labelledby="setup-title">
      <div className="px-4 py-3 border-b border-slate-200 bg-white flex items-center gap-2">
        <ShieldCheck className="h-5 w-5 text-brand-600" aria-hidden />
        <div>
          <h1 id="setup-title" className="text-sm font-semibold">
            Welcome to Once
          </h1>
          <p className="text-[10px] text-slate-500">Sign in to your backend and choose a vault passphrase.</p>
        </div>
      </div>
      <form onSubmit={(e) => void onSubmit(e)} className="p-4 space-y-3 text-xs">
        <div>
          <label className="label" htmlFor="setup-api">
            Backend URL
          </label>
          <input
            id="setup-api"
            className="input"
            value={apiBase}
            onChange={(e) => setApiBaseInput(e.target.value)}
            disabled={busy}
            autoComplete="off"
            required
          />
        </div>
        <div>
          <label className="label" htmlFor="setup-email">
            Email
          </label>
          <input
            id="setup-email"
            type="email"
            className="input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={busy}
            autoComplete="username"
            required
          />
        </div>
        <div>
          <label className="label" htmlFor="setup-password">
            Password
          </label>
          <input
            id="setup-password"
            type="password"
            className="input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={busy}
            autoComplete="current-password"
            required
          />
        </div>
        <div className="border-t border-slate-200 pt-3">
          <div>
            <label className="label" htmlFor="setup-pass">
              Vault passphrase
            </label>
            <input
              id="setup-pass"
              type="password"
              className="input"
              value={passphrase}
              onChange={(e) => setPassphrase(e.target.value)}
              disabled={busy}
              autoComplete="new-password"
              required
              minLength={8}
            />
          </div>
          <div className="mt-2">
            <label className="label" htmlFor="setup-confirm">
              Confirm passphrase
            </label>
            <input
              id="setup-confirm"
              type="password"
              className="input"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              disabled={busy}
              autoComplete="new-password"
              required
              minLength={8}
            />
          </div>
          <p className="mt-1 text-[10px] text-slate-500">
            We never send this to the server. Lose it and you will need to re-set up.
          </p>
        </div>

        {error ? (
          <div className="text-[11px] text-red-700 bg-red-50 border border-red-200 rounded px-2 py-1">{error}</div>
        ) : null}

        <button type="submit" className="btn-primary w-full" disabled={busy}>
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> : null}
          {busy ? "Signing in…" : "Sign in & unlock"}
        </button>
      </form>
    </section>
  );
}
