# VAULT_PASSKEY_DESIGN.md — FIDO2 / passkey as a second unlock factor

> **Status: design only.** This document specifies the intended design for
> adding FIDO2/passkey unlock to the Once extension vault. No code in
> `extension/src/` changes as a result of this document. Implementation
> requires explicit CONTRACTS.md review because it sits adjacent to the
> locked KDF parameters.

## Constraints we will not violate

Pulled from `CONTRACTS.md` §10 and `extension/AGENTS.md`:

1. PBKDF2-SHA256 @ 310,000 iterations is **locked**. Existing vaults
   continue to derive their master key exactly this way.
2. The derived master key remains `extractable: false`.
3. All cipher operations remain AES-GCM-256.
4. The vault remains local-only — no key material leaves the device.
5. The sentinel verifier semantics remain unchanged.

## Why we add passkeys (and why as a _second_ factor, not a replacement)

**Problem the passkey solves:** for high-security tenants
(`Extension-Only` tier — see `docs/PRICING_TIERS.md`), even a strong
passphrase is a weak link if the user types it on a compromised keyboard.
Passkeys move the unlock secret onto a hardware-backed authenticator
(Touch ID, Windows Hello, YubiKey).

**Why not replace the passphrase:** the passphrase IS the key-derivation
input today; existing vaults are derived from it. Replacing it would
require re-encrypting every existing vault, which is a coordinated
migration we won't undertake casually. Layering — passkey _wraps_
the passphrase-derived key — preserves backwards compatibility.

## Design — key wrapping envelope

We add a new optional field to the vault record (currently in IndexedDB):

```
VaultEnvelope {
  version: 2                        // bumped from 1
  salt: bytes(16)                   // unchanged
  sentinel_iv: bytes(12)            // unchanged
  sentinel_ct: bytes                // unchanged
  kdf: {
    algorithm: 'PBKDF2-SHA256'
    iterations: 310000              // LOCKED, do not change
  }
  passkey_wraps: PasskeyWrap[]      // NEW. Empty if no passkeys enrolled.
}

PasskeyWrap {
  credential_id: string             // FIDO2 credential ID (base64url)
  wrap_iv: bytes(12)
  wrap_ct: bytes                    // AES-GCM(K_wrap, master_key_bytes)
  rp_id: string                     // relying-party ID (e.g. 'getonce.com')
  created_at: ISO8601
}
```

Where `K_wrap` is derived per-passkey by running a deterministic operation
against the authenticator (see "K_wrap derivation" below).

### Unlock flow with a passkey enrolled

1. User opens the popup; extension reads `VaultEnvelope`.
2. If `passkey_wraps` is non-empty AND `navigator.credentials.get` is
   available: attempt passkey unlock first.
3. Browser prompts the user; on success, the extension obtains a per-call
   secret from the authenticator (see derivation).
4. Use that secret to derive `K_wrap`, then AES-GCM-decrypt one of the
   `wrap_ct` entries to recover the master key bytes.
5. Re-import the bytes as a non-extractable `CryptoKey`.
6. Verify against the sentinel as today. On success, vault is open.
7. If passkey unlock fails (cancelled, no credential, malformed wrap),
   fall back to the standard passphrase flow.

### Unlock flow without a passkey enrolled

Unchanged from today. Passphrase → PBKDF2 → master key → sentinel verify.

### K_wrap derivation

Two acceptable strategies, to be selected after the security-review pass:

**Option A — `prf` extension (preferred where supported).** Use the WebAuthn
`prf` extension to obtain a 32-byte secret bound to the credential. HKDF that
secret with a vault-specific salt to produce `K_wrap`. This is the
RFC-track-aligned approach and is supported in Chromium ≥123 for platform
authenticators.

**Option B — `largeBlob`.** Store an envelope-encrypted random `K_wrap`
inside the authenticator's `largeBlob` store. Less portable across
authenticators; use only if PRF is unavailable.

Whichever is chosen, the derived `K_wrap` must:

- Never be persisted.
- Be discarded immediately after wrapping/unwrapping.
- Be obtained anew for every unlock.

## Enrollment flow

1. User opens vault settings → "Add hardware unlock."
2. Extension requires the user to enter the **current passphrase** to
   prove they hold the master key.
3. With the master key in memory, extension calls
   `navigator.credentials.create({ publicKey: { ... } })` with the chosen
   `prf` / `largeBlob` extension enabled.
4. Derives `K_wrap` from the new credential.
5. AES-GCM-encrypts the master key bytes with `K_wrap`, producing a new
   `PasskeyWrap` entry.
6. Persists the updated `VaultEnvelope` (version bumped to 2 if needed).

## Removal flow

1. User opens vault settings → "Manage hardware unlocks" → "Remove."
2. User confirms with current passphrase OR with another enrolled passkey.
3. Extension removes the corresponding `PasskeyWrap` entry. The credential
   on the authenticator itself is left intact (we don't have authority to
   delete it).

## Backwards compatibility

- Vaults at `version: 1` continue to work indefinitely. Upgrade to v2 is
  triggered only on the first passkey enrollment.
- Removing all enrolled passkeys downgrades the envelope to v1-equivalent
  (`passkey_wraps: []`), but the version number is not decremented to
  avoid confusing the migration logic.

## Threat-model deltas

| Threat                                                 | Pre-passkey             | Post-passkey (with passkey enrolled)                                |
| ------------------------------------------------------ | ----------------------- | ------------------------------------------------------------------- |
| Compromised keyboard reads passphrase                  | Vault is compromised    | Passphrase alone insufficient if user prefers passkey               |
| Stolen laptop with auto-lock disabled                  | Vault contents readable | Still readable — passkey doesn't help against an already-open vault |
| Authenticator physical theft + known passphrase        | Same as before          | No worse than before; passkey is at most equivalent to passphrase   |
| Backend compromise                                     | Cannot read vault       | Cannot read vault                                                   |
| Malicious extension reads sentinel + tries passphrases | Bounded by PBKDF2 cost  | Same; passkey doesn't change passphrase brute-force economics       |

## Open questions for security review

1. Should we _require_ the passkey when one is enrolled (no passphrase
   fallback)? Argument for: removes the weakest link. Argument against:
   account-recovery becomes much harder.
2. Should `K_wrap` derivation include a server-side challenge? Pro: ties
   the unlock to a fresh network event. Con: re-introduces an online
   dependency the extension proudly avoids.
3. Cross-device sync of passkeys (iCloud Keychain, Google Password
   Manager) — do we allow it? Default proposal: yes, since the
   authenticator's local biometric still gates use.

## Implementation gate

This document does NOT authorize implementation. Before any code lands:

1. CONTRACTS.md §10 review and amendment (if any).
2. Security review pass against this document.
3. `docs/PENTEST_BRIEF.md` updated to include passkey flows in scope.
4. Migration plan for the v1 → v2 envelope (no-op for existing users).

## See also

- [extension/AGENTS.md](../extension/AGENTS.md) — extension engineering rules.
- [CONTRACTS.md](../CONTRACTS.md) §10 — locked KDF parameters.
- [docs/PENTEST_BRIEF.md](./PENTEST_BRIEF.md) — pen-test scope.
- [docs/PRICING_TIERS.md](./PRICING_TIERS.md) — Extension-Only tier this serves.
