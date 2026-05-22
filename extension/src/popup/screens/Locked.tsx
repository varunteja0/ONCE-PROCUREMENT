import React, { useState } from "react";
import { Loader2, LockKeyhole } from "lucide-react";

import { unlock as vaultUnlock, VaultPassphraseError } from "../../lib/vault";
import { send } from "../../lib/messaging";

export function Locked({
  onUnlocked,
}: {
  onUnlocked: () => void | Promise<void>;
}): JSX.Element {
  const [passphrase, setPassphrase] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    if (!passphrase) return;
    setBusy(true);
    setError(null);
    try {
      await vaultUnlock(passphrase);
      await send({ type: "vault.unlock", passphrase });
      setPassphrase("");
      await onUnlocked();
    } catch (err) {
      if (err instanceof VaultPassphraseError) {
        setError("Wrong passphrase.");
      } else {
        setError(err instanceof Error ? err.message : "unlock_failed");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <section
      className="flex-1 flex flex-col items-center justify-center p-6"
      aria-labelledby="locked-title"
    >
      <div className="mb-3 h-10 w-10 rounded-full bg-amber-100 flex items-center justify-center">
        <LockKeyhole className="h-5 w-5 text-amber-700" aria-hidden />
      </div>
      <h1 id="locked-title" className="text-sm font-semibold">Vault locked</h1>
      <p className="text-[11px] text-slate-500 mb-3 text-center">
        Enter your passphrase to decrypt local data.
      </p>
      <form onSubmit={(e) => void onSubmit(e)} className="w-full space-y-2">
        <label htmlFor="unlock-pass" className="sr-only">Passphrase</label>
        <input
          id="unlock-pass"
          type="password"
          className="input"
          value={passphrase}
          onChange={(e) => setPassphrase(e.target.value)}
          disabled={busy}
          autoFocus
          autoComplete="current-password"
          required
        />
        {error ? (
          <div className="text-[11px] text-red-700">{error}</div>
        ) : null}
        <button
          type="submit"
          className="btn-primary w-full"
          disabled={busy || passphrase.length === 0}
        >
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> : null}
          {busy ? "Unlocking…" : "Unlock"}
        </button>
      </form>
    </section>
  );
}
