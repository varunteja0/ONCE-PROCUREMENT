// requires `fake-indexeddb` devDep — add to package.json if missing
// (Agent 15's package.json may not list it; install with
// `npm i -D fake-indexeddb` so this test can run.)
import "fake-indexeddb/auto";

import { beforeEach, describe, expect, it } from "vitest";

import {
  __test__,
  getProfile,
  init,
  isInitialized,
  lock,
  putProfile,
  unlock,
  VaultLockedError,
  VaultPassphraseError,
} from "../src/lib/vault";
import type { SupplierProfile } from "../src/types/profile";

const PASSPHRASE = "correct horse battery staple";
const WRONG_PASSPHRASE = "incorrect horse battery staple";
const PROFILE_KEY = "default";

function sampleProfile(): SupplierProfile {
  return {
    legal_name: "Acme Insurance Brokers LLC",
    dba_name: "Acme",
    ein: "12-3456789",
    naics_code: "524210",
    primary_email: "ops@acme.example",
    primary_phone: "+1-415-555-0142",
    address: {
      line1: "100 Market St",
      city: "San Francisco",
      region: "CA",
      postal_code: "94105",
      country: "US",
    },
    website: "https://acme.example",
    coi: {
      carrier: "Hartford",
      policy_number: "POL-0001",
      expiry: "2026-01-01",
      limit_each_occurrence: 1_000_000,
      limit_aggregate: 2_000_000,
    },
    lines_of_business: ["workers_comp", "general_liability"],
    license_states: ["CA", "NY"],
    npn: "1234567",
  };
}

beforeEach(async () => {
  await __test__._wipe();
});

describe("vault", () => {
  it("init persists state and reports isInitialized=true", async () => {
    expect(await isInitialized()).toBe(false);
    await init(PASSPHRASE);
    expect(await isInitialized()).toBe(true);
    expect(__test__.getSessionKey()).not.toBeNull();
  });

  it("putProfile + getProfile round-trip returns identical profile", async () => {
    await init(PASSPHRASE);
    const profile = sampleProfile();
    await putProfile(PROFILE_KEY, profile);
    const loaded = await getProfile(PROFILE_KEY);
    expect(loaded).toEqual(profile);
  });

  it("lock clears the session key and blocks vault reads/writes", async () => {
    await init(PASSPHRASE);
    await putProfile(PROFILE_KEY, sampleProfile());
    lock();
    expect(__test__.getSessionKey()).toBeNull();
    await expect(getProfile(PROFILE_KEY)).rejects.toBeInstanceOf(
      VaultLockedError,
    );
    await expect(putProfile(PROFILE_KEY, sampleProfile())).rejects.toBeInstanceOf(
      VaultLockedError,
    );
  });

  it("unlock with wrong passphrase fails with VaultPassphraseError", async () => {
    await init(PASSPHRASE);
    lock();
    await expect(unlock(WRONG_PASSPHRASE)).rejects.toBeInstanceOf(
      VaultPassphraseError,
    );
    expect(__test__.getSessionKey()).toBeNull();
  });

  it("unlock with right passphrase restores access; getProfile returns identical data", async () => {
    await init(PASSPHRASE);
    const original = sampleProfile();
    await putProfile(PROFILE_KEY, original);
    lock();

    const session = await unlock(PASSPHRASE);
    expect(session).not.toBeNull();
    expect(__test__.getSessionKey()).not.toBeNull();

    const loaded = await getProfile(PROFILE_KEY);
    expect(loaded).toEqual(original);
  });
});
