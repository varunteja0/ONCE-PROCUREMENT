/**
 * Top-level popup.
 *
 * Flow
 * ----
 *  1. On mount: read tokens + vault-initialized + vault-unlocked +
 *     active tab id + cached suppliers/submissions.
 *  2. Route:
 *       no tokens               → <Setup>
 *       tokens, vault locked    → <Locked>
 *       tokens, vault unlocked  → <Home|Suppliers|Submissions|Activity>
 *  3. Top-right buttons: lock (when unlocked) + settings (always).
 */
import { useCallback, useEffect, useState } from "react";

import type { SubmissionListItem, UserMe } from "../lib/api";
import type { PortalDetection } from "../lib/messaging";
import { send } from "../lib/messaging";
import { clearTokens, getTokens } from "../lib/storage";
import { usePopupStore, type Screen } from "../lib/store";
import { getCachedSubmissions, getCachedSuppliers } from "../lib/sync";
import { __test__ as vaultDebug, isInitialized as vaultIsInitialized, lock as vaultLock } from "../lib/vault";

import { Nav } from "./components/Nav";
import { Banner, Header, Shell } from "./components/Shell";
import { Activity } from "./screens/Activity";
import { Home } from "./screens/Home";
import { Locked } from "./screens/Locked";
import { Receipts } from "./screens/Receipts";
import { Setup } from "./screens/Setup";
import { Submissions } from "./screens/Submissions";
import { Suppliers } from "./screens/Suppliers";

interface BootState {
  hasTokens: boolean;
  vaultInitialized: boolean;
  vaultUnlocked: boolean;
  user: UserMe | null;
  tabId: number | null;
  detection: PortalDetection | null;
}

async function bootstrap(): Promise<BootState> {
  const [tokens, vaultInitialized] = await Promise.all([getTokens(), vaultIsInitialized()]);
  const vaultUnlocked = vaultDebug.getSessionKey() !== null;

  let tabId: number | null = null;
  let detection: PortalDetection | null = null;
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    tabId = typeof tab?.id === "number" ? tab.id : null;
    if (tabId !== null) {
      const resp = await send({ type: "portal.active", tabId });
      if (resp.ok) detection = resp.detection;
    }
  } catch {
    /* ignore — non-extension contexts */
  }

  let user: UserMe | null = null;
  if (tokens) {
    try {
      const resp = await send({ type: "auth.me" });
      if (resp.ok) user = resp.user;
    } catch {
      /* network — handled by UI */
    }
  }

  return {
    hasTokens: !!tokens,
    vaultInitialized,
    vaultUnlocked,
    user,
    tabId,
    detection,
  };
}

export function App(): JSX.Element {
  const screen = usePopupStore((s) => s.screen);
  const setScreen = usePopupStore((s) => s.setScreen);
  const setTabId = usePopupStore((s) => s.setTabId);
  const setDetection = usePopupStore((s) => s.setDetection);
  const setSuppliers = usePopupStore((s) => s.setSuppliers);
  const setVaultUnlocked = usePopupStore((s) => s.setVaultUnlocked);
  const setHasConnection = usePopupStore((s) => s.setHasConnection);
  const banner = usePopupStore((s) => s.banner);
  const setBanner = usePopupStore((s) => s.setBanner);
  const suppliers = usePopupStore((s) => s.suppliers);
  const detection = usePopupStore((s) => s.detection);

  const [user, setUser] = useState<UserMe | null>(null);
  const [submissions, setSubmissions] = useState<SubmissionListItem[]>([]);
  const [boot, setBoot] = useState<"loading" | "setup" | "locked" | "ready">("loading");

  const refresh = useCallback(async (): Promise<void> => {
    const state = await bootstrap();
    setTabId(state.tabId);
    setDetection(state.detection);
    setVaultUnlocked(state.vaultUnlocked);
    setHasConnection(state.hasTokens);
    setUser(state.user);

    if (!state.hasTokens || !state.vaultInitialized) {
      setBoot("setup");
      setScreen("home");
      return;
    }
    if (!state.vaultUnlocked) {
      setBoot("locked");
      return;
    }
    setBoot("ready");
    const [cs, ss] = await Promise.all([getCachedSuppliers(), getCachedSubmissions()]);
    setSuppliers(cs);
    setSubmissions(ss);
  }, [setBoot, setDetection, setHasConnection, setScreen, setSubmissions, setSuppliers, setTabId, setVaultUnlocked]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (typeof chrome === "undefined" || !chrome.runtime?.onMessage) {
      return undefined;
    }
    const listener = (
      message: unknown,
      _sender: chrome.runtime.MessageSender,
      sendResponse: (response: { ok: true }) => void,
    ): boolean => {
      if (typeof message !== "object" || message === null || (message as { type?: unknown }).type !== "vault.lock") {
        return false;
      }
      vaultLock();
      setVaultUnlocked(false);
      setBoot("locked");
      sendResponse({ ok: true });
      return false;
    };
    chrome.runtime.onMessage.addListener(listener);
    return (): void => chrome.runtime.onMessage.removeListener(listener);
  }, [setVaultUnlocked]);

  // Auto-dismiss banner after 4s.
  useEffect(() => {
    if (!banner) return;
    const t = setTimeout(() => setBanner(null), 4000);
    return (): void => clearTimeout(t);
  }, [banner, setBanner]);

  const onLock = useCallback(async () => {
    vaultLock();
    await send({ type: "vault.lock" });
    setVaultUnlocked(false);
    setBoot("locked");
  }, [setVaultUnlocked]);

  const onSettings = useCallback(() => {
    try {
      chrome.runtime.openOptionsPage();
    } catch {
      /* test env */
    }
  }, []);

  const onLogout = useCallback(async () => {
    await clearTokens();
    await send({ type: "auth.disconnect" });
    await refresh();
  }, [refresh]);

  // ---- render ------------------------------------------------------------
  if (boot === "loading") {
    return (
      <Shell>
        <Header onSettings={onSettings} />
        <div className="flex-1 flex items-center justify-center text-xs text-slate-500">Loading…</div>
      </Shell>
    );
  }

  if (boot === "setup") {
    return (
      <Shell>
        <Header onSettings={onSettings} />
        <Setup onDone={() => void refresh()} />
      </Shell>
    );
  }

  if (boot === "locked") {
    return (
      <Shell>
        <Header email={user?.email ?? null} onSettings={onSettings} />
        <Locked onUnlocked={() => void refresh()} />
      </Shell>
    );
  }

  return (
    <Shell>
      <Header email={user?.email ?? null} onSettings={onSettings} onLock={() => void onLock()} lockable />
      {banner ? <Banner kind={banner.kind} text={banner.text} /> : null}
      <Nav current={screen} onChange={(s: Screen) => setScreen(s)} />
      <main className="flex-1 overflow-y-auto" aria-live="polite">
        {screen === "home" ? <Home suppliers={suppliers} detection={detection} /> : null}
        {screen === "suppliers" ? <Suppliers suppliers={suppliers} onRefreshed={setSuppliers} /> : null}
        {screen === "submissions" ? <Submissions submissions={submissions} /> : null}
        {screen === "receipts" ? <Receipts /> : null}
        {screen === "activity" ? <Activity /> : null}
      </main>
      <footer className="border-t border-slate-200 bg-white px-3 py-1.5 flex items-center justify-between">
        <span className="text-[10px] text-slate-400">
          v{typeof __APP_VERSION__ === "string" ? __APP_VERSION__ : "dev"}
        </span>
        <button
          type="button"
          className="text-[10px] text-slate-500 hover:text-slate-800 underline"
          onClick={() => void onLogout()}
        >
          Sign out
        </button>
      </footer>
    </Shell>
  );
}
