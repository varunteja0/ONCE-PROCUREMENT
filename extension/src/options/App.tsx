/**
 * Options page — full-page settings UI.
 *
 * Sections:
 *   1. Connection  — API base URL + access token.
 *   2. Security    — auto-lock duration (1–240 minutes, default 15).
 *   3. Defaults    — default supplier per portal map (free-form pairs).
 *   4. Telemetry   — informational read-only notice.
 *   5. Vault       — clear (type-to-confirm), export, import.
 *
 * Storage uses the same keys as the popup so settings are visible
 * everywhere immediately. The page never sees plaintext vault data.
 */
import { useEffect, useState } from "react";
import { Download, Save, ShieldCheck, Trash2, Upload } from "lucide-react";

import { send } from "../lib/messaging";
import {
  DEFAULT_API_BASE,
  STORAGE_KEYS,
  clearTokens,
  getApiBase,
  setApiBase,
  setTokens,
  storageGet,
  storageRemove,
  storageSet,
} from "../lib/storage";
import { lock as vaultLock } from "../lib/vault";

interface PortalDefault {
  portal: string;
  supplierId: string;
}

const VAULT_DB = "once_vault";

export function App(): JSX.Element {
  // ---- state ----
  const [apiBase, setApiBaseState] = useState(DEFAULT_API_BASE);
  const [accessToken, setAccessToken] = useState("");
  const [autoLock, setAutoLock] = useState(15);
  const [defaults, setDefaults] = useState<PortalDefault[]>([]);
  const [confirmDelete, setConfirmDelete] = useState("");
  const [banner, setBanner] = useState<{
    kind: "ok" | "err";
    text: string;
  } | null>(null);
  const [busy, setBusy] = useState(false);

  // ---- load ----
  useEffect(() => {
    void (async () => {
      const [base, lock, map] = await Promise.all([
        getApiBase(),
        storageGet<number>(STORAGE_KEYS.autoLockMinutes, 15),
        storageGet<Record<string, string>>(
          STORAGE_KEYS.defaultSupplierPerPortal,
          {},
        ),
      ]);
      setApiBaseState(base);
      setAutoLock(typeof lock === "number" && lock > 0 ? lock : 15);
      setDefaults(
        Object.entries(map ?? {}).map(([portal, supplierId]) => ({
          portal,
          supplierId,
        })),
      );
    })();
  }, []);

  useEffect(() => {
    if (!banner) return;
    const t = setTimeout(() => setBanner(null), 3500);
    return (): void => clearTimeout(t);
  }, [banner]);

  // ---- actions ----
  const onSaveConnection = async (): Promise<void> => {
    setBusy(true);
    try {
      const base = apiBase.trim() || DEFAULT_API_BASE;
      await setApiBase(base);
      if (accessToken.trim().length > 0) {
        await setTokens({
          access: accessToken.trim(),
          refresh: accessToken.trim(),
        });
        const resp = await send({
          type: "auth.connect",
          apiBase: base,
          accessToken: accessToken.trim(),
        });
        if (!resp.ok) {
          setBanner({ kind: "err", text: `Validation failed: ${resp.error}` });
          return;
        }
        setAccessToken("");
      }
      setBanner({ kind: "ok", text: "Connection saved." });
    } finally {
      setBusy(false);
    }
  };

  const onSaveAutoLock = async (): Promise<void> => {
    const n = Math.min(240, Math.max(1, Math.floor(autoLock)));
    await storageSet(STORAGE_KEYS.autoLockMinutes, n);
    setAutoLock(n);
    setBanner({ kind: "ok", text: `Auto-lock set to ${n} minutes.` });
  };

  const onSaveDefaults = async (): Promise<void> => {
    const map: Record<string, string> = {};
    for (const { portal, supplierId } of defaults) {
      const p = portal.trim();
      const s = supplierId.trim();
      if (p.length > 0 && s.length > 0) map[p] = s;
    }
    await storageSet(STORAGE_KEYS.defaultSupplierPerPortal, map);
    setBanner({ kind: "ok", text: "Defaults saved." });
  };

  const onAddDefault = (): void => {
    setDefaults((d) => [...d, { portal: "", supplierId: "" }]);
  };

  const onRemoveDefault = (idx: number): void => {
    setDefaults((d) => d.filter((_, i) => i !== idx));
  };

  const onClearVault = async (): Promise<void> => {
    if (confirmDelete !== "DELETE") {
      setBanner({ kind: "err", text: 'Type DELETE to confirm.' });
      return;
    }
    setBusy(true);
    try {
      vaultLock();
      await clearTokens();
      await storageRemove(STORAGE_KEYS.vaultInitialized);
      await storageRemove(STORAGE_KEYS.vaultSalt);
      await storageRemove(STORAGE_KEYS.vaultUnlockedAt);
      await send({ type: "vault.lock" });
      await deleteIDB(VAULT_DB);
      setConfirmDelete("");
      setBanner({ kind: "ok", text: "Vault cleared." });
    } catch (err) {
      setBanner({
        kind: "err",
        text: err instanceof Error ? err.message : "clear_failed",
      });
    } finally {
      setBusy(false);
    }
  };

  const onExportVault = async (): Promise<void> => {
    try {
      const dump = await dumpIDB(VAULT_DB);
      const blob = new Blob([JSON.stringify(dump, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `once-vault-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setBanner({ kind: "ok", text: "Vault exported." });
    } catch (err) {
      setBanner({
        kind: "err",
        text: err instanceof Error ? err.message : "export_failed",
      });
    }
  };

  const onImportVault = async (file: File): Promise<void> => {
    try {
      const text = await file.text();
      const parsed = JSON.parse(text) as IdbDump;
      await restoreIDB(VAULT_DB, parsed);
      setBanner({
        kind: "ok",
        text: "Vault imported. Unlock from the popup with your passphrase.",
      });
    } catch (err) {
      setBanner({
        kind: "err",
        text: err instanceof Error ? err.message : "import_failed",
      });
    }
  };

  // ---- render ----
  return (
    <div className="mx-auto max-w-2xl p-6 space-y-6 font-sans text-sm">
      <header className="flex items-center gap-3 pb-3 border-b border-slate-200">
        <ShieldCheck className="h-6 w-6 text-brand-600" aria-hidden />
        <div>
          <h1 className="text-lg font-semibold">Once — Settings</h1>
          <p className="text-xs text-slate-500">
            All values are stored locally. Nothing on this page is sent anywhere
            except your configured backend.
          </p>
        </div>
      </header>

      {banner ? (
        <div
          role="status"
          className={`rounded border px-3 py-2 text-xs ${
            banner.kind === "ok"
              ? "bg-emerald-50 text-emerald-800 border-emerald-200"
              : "bg-red-50 text-red-800 border-red-200"
          }`}
        >
          {banner.text}
        </div>
      ) : null}

      {/* ---- Connection ---- */}
      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Connection</h2>
        <div>
          <label className="label" htmlFor="opt-api">
            Backend URL
          </label>
          <input
            id="opt-api"
            className="input"
            value={apiBase}
            onChange={(e) => setApiBaseState(e.target.value)}
            placeholder={DEFAULT_API_BASE}
          />
        </div>
        <div>
          <label className="label" htmlFor="opt-token">
            New access token (leave blank to keep current)
          </label>
          <input
            id="opt-token"
            type="password"
            className="input font-mono"
            value={accessToken}
            onChange={(e) => setAccessToken(e.target.value)}
            autoComplete="off"
          />
        </div>
        <button
          type="button"
          className="btn-primary"
          onClick={() => void onSaveConnection()}
          disabled={busy}
        >
          <Save className="h-3.5 w-3.5" aria-hidden /> Save connection
        </button>
      </section>

      {/* ---- Security ---- */}
      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Security</h2>
        <div>
          <label className="label" htmlFor="opt-lock">
            Auto-lock after (minutes of inactivity)
          </label>
          <select
            id="opt-lock"
            className="input"
            value={autoLock}
            onChange={(e) => setAutoLock(Number(e.target.value))}
          >
            <option value={5}>5</option>
            <option value={15}>15</option>
            <option value={30}>30</option>
            <option value={60}>60</option>
          </select>
        </div>
        <button
          type="button"
          className="btn-primary"
          onClick={() => void onSaveAutoLock()}
        >
          <Save className="h-3.5 w-3.5" aria-hidden /> Save auto-lock
        </button>
      </section>

      {/* ---- Default supplier per portal ---- */}
      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Default supplier per portal</h2>
        <p className="text-xs text-slate-500">
          When a new tab loads a supported portal, the matching supplier here is
          pre-selected. Portal must be one of the platform ids (e.g.
          <code className="font-mono text-[11px]"> applied_epic</code>).
        </p>
        <ul className="space-y-2">
          {defaults.map((d, idx) => (
            <li key={idx} className="flex gap-2 items-end">
              <div className="flex-1">
                <label className="label">Portal</label>
                <input
                  className="input"
                  value={d.portal}
                  onChange={(e) =>
                    setDefaults((arr) => {
                      const next = [...arr];
                      const cur = next[idx];
                      if (cur) next[idx] = { ...cur, portal: e.target.value };
                      return next;
                    })
                  }
                />
              </div>
              <div className="flex-1">
                <label className="label">Supplier id</label>
                <input
                  className="input font-mono"
                  value={d.supplierId}
                  onChange={(e) =>
                    setDefaults((arr) => {
                      const next = [...arr];
                      const cur = next[idx];
                      if (cur)
                        next[idx] = { ...cur, supplierId: e.target.value };
                      return next;
                    })
                  }
                />
              </div>
              <button
                type="button"
                className="btn-ghost h-8 px-2"
                onClick={() => onRemoveDefault(idx)}
                aria-label="Remove"
              >
                <Trash2 className="h-3.5 w-3.5" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
        <div className="flex gap-2">
          <button type="button" className="btn-secondary" onClick={onAddDefault}>
            + Add
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={() => void onSaveDefaults()}
          >
            <Save className="h-3.5 w-3.5" aria-hidden /> Save defaults
          </button>
        </div>
      </section>

      {/* ---- Telemetry ---- */}
      <section className="space-y-1">
        <h2 className="text-sm font-semibold">Telemetry</h2>
        <p className="text-xs text-slate-500">
          Always off — nothing is sent to GitHub, the Once team, or any third
          party. All API requests go to the backend URL above and nowhere else.
        </p>
      </section>

      {/* ---- Vault management ---- */}
      <section className="space-y-2 border-t border-slate-200 pt-4">
        <h2 className="text-sm font-semibold">Vault</h2>
        <div className="flex gap-2">
          <button
            type="button"
            className="btn-secondary"
            onClick={() => void onExportVault()}
          >
            <Download className="h-3.5 w-3.5" aria-hidden /> Export vault (JSON)
          </button>
          <label className="btn-secondary cursor-pointer">
            <Upload className="h-3.5 w-3.5" aria-hidden /> Import vault
            <input
              type="file"
              accept="application/json"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void onImportVault(f);
              }}
            />
          </label>
        </div>
        <p className="text-xs text-slate-500">
          The exported file is the encrypted IndexedDB store — opening it
          without your passphrase reveals nothing.
        </p>

        <div className="mt-4 rounded border border-red-200 bg-red-50 p-3 space-y-2">
          <div className="text-xs font-semibold text-red-800">Danger zone</div>
          <p className="text-[11px] text-red-700">
            Clearing the vault wipes all encrypted entries, tokens, and the
            stored API base. Type{" "}
            <code className="font-mono">DELETE</code> to confirm.
          </p>
          <input
            className="input"
            value={confirmDelete}
            onChange={(e) => setConfirmDelete(e.target.value)}
            placeholder="DELETE"
            aria-label="Confirm by typing DELETE"
          />
          <button
            type="button"
            className="btn-danger"
            onClick={() => void onClearVault()}
            disabled={busy || confirmDelete !== "DELETE"}
          >
            <Trash2 className="h-3.5 w-3.5" aria-hidden /> Clear vault
          </button>
        </div>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// IndexedDB helpers — generic dump/restore so we don't need to know the schema
// ---------------------------------------------------------------------------

interface IdbStoreDump {
  name: string;
  keyPath: string | string[] | null;
  records: { key: IDBValidKey; value: unknown }[];
}

interface IdbDump {
  db: string;
  version: number;
  stores: IdbStoreDump[];
}

function openExisting(name: string): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(name);
    req.onsuccess = (): void => resolve(req.result);
    req.onerror = (): void =>
      reject(req.error ?? new Error("idb open failed"));
  });
}

async function dumpIDB(name: string): Promise<IdbDump> {
  const db = await openExisting(name);
  const storeNames = Array.from(db.objectStoreNames);
  const stores: IdbStoreDump[] = [];
  for (const sn of storeNames) {
    const tx = db.transaction(sn, "readonly");
    const store = tx.objectStore(sn);
    const keys = await reqToPromise<IDBValidKey[]>(store.getAllKeys());
    const values = await reqToPromise<unknown[]>(store.getAll());
    const records = keys.map((key, i) => ({ key, value: values[i] }));
    stores.push({ name: sn, keyPath: store.keyPath ?? null, records });
  }
  const dump: IdbDump = { db: name, version: db.version, stores };
  db.close();
  return dump;
}

async function restoreIDB(name: string, dump: IdbDump): Promise<void> {
  if (dump.db !== name) throw new Error("dump db name mismatch");
  await deleteIDB(name);
  await new Promise<void>((resolve, reject) => {
    const req = indexedDB.open(name, dump.version);
    req.onupgradeneeded = (): void => {
      const db = req.result;
      for (const s of dump.stores) {
        if (!db.objectStoreNames.contains(s.name)) {
          if (s.keyPath !== null) {
            db.createObjectStore(s.name, { keyPath: s.keyPath });
          } else {
            db.createObjectStore(s.name);
          }
        }
      }
    };
    req.onsuccess = async (): Promise<void> => {
      const db = req.result;
      try {
        for (const s of dump.stores) {
          const tx = db.transaction(s.name, "readwrite");
          const store = tx.objectStore(s.name);
          for (const r of s.records) {
            if (store.keyPath === null) {
              await reqToPromise(store.put(r.value, r.key));
            } else {
              await reqToPromise(store.put(r.value));
            }
          }
        }
        db.close();
        resolve();
      } catch (e) {
        reject(e);
      }
    };
    req.onerror = (): void =>
      reject(req.error ?? new Error("idb open failed"));
  });
}

function deleteIDB(name: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.deleteDatabase(name);
    req.onsuccess = (): void => resolve();
    req.onerror = (): void =>
      reject(req.error ?? new Error("idb delete failed"));
    req.onblocked = (): void => resolve();
  });
}

function reqToPromise<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = (): void => resolve(req.result);
    req.onerror = (): void =>
      reject(req.error ?? new Error("idb req failed"));
  });
}
