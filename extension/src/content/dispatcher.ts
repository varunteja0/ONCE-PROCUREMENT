/**
 * Content-script entry point. Runs once per page load (idempotent), detects
 * the carrier portal from `window.location.hostname`, loads the active
 * supplier profile from the background service-worker / vault, invokes the
 * matching filler, and surfaces an in-page toast plus a `FILL_REPORT`
 * message back to the background for telemetry.
 */
import type { SupplierProfile } from "../types/profile";
import { isSupplierProfile } from "../types/profile";
import type { PortalPlatform } from "../types/portal";
import { send } from "../lib/messaging";
import * as appliedEpic from "./fillers/applied_epic";
import * as amtrust from "./fillers/amtrust";
import * as markel from "./fillers/markel";
import type { FillerFn, FillReport, FillerContext } from "./fillers/_shared";

// ---------------------------------------------------------------------------
// Idempotency guard — content scripts can be re-injected
// ---------------------------------------------------------------------------

interface OnceWindow {
  __once_dispatcher_ran__?: true;
}

// ---------------------------------------------------------------------------
// Portal detection (mirrors backend `app/automation/detector.py`)
// ---------------------------------------------------------------------------

interface HostRule {
  pattern: RegExp;
  platform: PortalPlatform;
}

const HOST_RULES: readonly HostRule[] = [
  { pattern: /(^|\.)appliedepic\.com$/i, platform: "applied_epic" },
  { pattern: /(^|\.)ams360\.com$/i, platform: "vertafore_ams360" },
  { pattern: /(^|\.)sircon\.com$/i, platform: "vertafore_sircon" },
  { pattern: /(^|\.)amtrustfinancial\.com$/i, platform: "amtrust" },
  { pattern: /^producers\.amtrust/i, platform: "amtrust" },
  { pattern: /(^|\.)markelcorp\.com$/i, platform: "markel" },
  { pattern: /^cnabrokerportal\.cna\.com$/i, platform: "cna" },
];

interface UrlRule {
  pattern: RegExp;
  platform: PortalPlatform;
}

const URL_RULES: readonly UrlRule[] = [
  { pattern: /markel\.com\/producers/i, platform: "markel" },
  { pattern: /nationwide\.com\/business/i, platform: "nationwide_es" },
];

function detectPortal(hostname: string, fullUrl: string): PortalPlatform | null {
  for (const rule of HOST_RULES) {
    if (rule.pattern.test(hostname)) return rule.platform;
  }
  for (const rule of URL_RULES) {
    if (rule.pattern.test(fullUrl)) return rule.platform;
  }
  return null;
}

// ---------------------------------------------------------------------------
// Message handler — popup-triggered fill ("Fill from supplier ..." button)
// ---------------------------------------------------------------------------

interface ContentFillMessage {
  type: "content.fill";
  profile: SupplierProfile;
  portal: PortalPlatform;
}

interface ContentFillResponse {
  ok: boolean;
  filled?: number;
  skipped?: number;
  error?: string;
}

function isContentFillMessage(value: unknown): value is ContentFillMessage {
  if (!value || typeof value !== "object") return false;
  const v = value as { type?: unknown };
  return v.type === "content.fill";
}

function registerFillListener(): void {
  if (
    typeof chrome === "undefined" ||
    !chrome.runtime ||
    !chrome.runtime.onMessage
  ) {
    return;
  }
  chrome.runtime.onMessage.addListener(
    (
      message: unknown,
      _sender: chrome.runtime.MessageSender,
      sendResponse: (response: ContentFillResponse) => void,
    ): boolean => {
      if (!isContentFillMessage(message)) return false;
      const filler = FILLERS[message.portal];
      if (!filler) {
        sendResponse({ ok: false, error: `no_filler:${message.portal}` });
        return false;
      }
      const ctx: FillerContext = {
        hostname: window.location.hostname,
        portal: message.portal,
        log: (m, extra) =>
          console.info(`[once.cs:${message.portal}] ${m}`, extra ?? {}),
      };
      void (async () => {
        try {
          const report = await filler(message.profile, ctx);
          sendResponse({
            ok: true,
            filled: report.filled.length,
            skipped: report.skipped.length,
          });
        } catch (err) {
          sendResponse({
            ok: false,
            error: err instanceof Error ? err.message : "filler_threw",
          });
        }
      })();
      return true; // async
    },
  );
}

// ---------------------------------------------------------------------------
// Filler registry
// ---------------------------------------------------------------------------

const FILLERS: Partial<Record<PortalPlatform, FillerFn>> = {
  applied_epic: appliedEpic.fill,
  amtrust: amtrust.fill,
  markel: markel.fill,
};

// ---------------------------------------------------------------------------
// Background messaging
// ---------------------------------------------------------------------------

interface FillReportMessage {
  type: "FILL_REPORT";
  portal: PortalPlatform;
  hostname: string;
  url: string;
  filled: string[];
  skipped: string[];
  durationMs: number;
}

async function loadProfile(): Promise<SupplierProfile | null> {
  try {
    const resp = await send({ type: "profile.active" });
    if (!resp.ok) return null;
    const profile = resp.profile;
    if (profile === null) return null;
    if (!isSupplierProfile(profile)) return null;
    return profile;
  } catch (err) {
    console.warn("[once.cs] failed to load profile", err);
    return null;
  }
}

async function reportToBackground(msg: FillReportMessage): Promise<void> {
  try {
    await chrome.runtime.sendMessage(msg);
  } catch (err) {
    console.warn("[once.cs] failed to send FILL_REPORT", err);
  }
}

// ---------------------------------------------------------------------------
// Floating toast (shadow-DOM isolated)
// ---------------------------------------------------------------------------

interface Toast {
  update(filled: number, total: number): void;
  finish(message: string): void;
  fail(message: string): void;
}

function mountToast(): Toast {
  const host = document.createElement("div");
  host.id = "once-toast-host";
  host.style.position = "fixed";
  host.style.zIndex = "2147483647";
  host.style.top = "16px";
  host.style.right = "16px";
  host.style.pointerEvents = "none";
  const shadow = host.attachShadow({ mode: "closed" });
  const wrap = document.createElement("div");
  wrap.setAttribute(
    "style",
    [
      "font: 13px/1.4 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif",
      "background: #111827",
      "color: #f9fafb",
      "padding: 10px 14px",
      "border-radius: 8px",
      "box-shadow: 0 8px 24px rgba(0,0,0,0.18)",
      "min-width: 220px",
      "pointer-events: auto",
    ].join(";"),
  );
  wrap.textContent = "Once: starting…";
  shadow.appendChild(wrap);
  document.documentElement.appendChild(host);

  let removeTimer: ReturnType<typeof setTimeout> | null = null;
  const scheduleRemoval = (ms: number): void => {
    if (removeTimer !== null) clearTimeout(removeTimer);
    removeTimer = setTimeout(() => host.remove(), ms);
  };

  return {
    update(filled: number, total: number) {
      wrap.textContent = `Once: filling ${filled}/${total} fields…`;
    },
    finish(message: string) {
      wrap.textContent = `Once: ${message}`;
      wrap.style.background = "#065f46";
      scheduleRemoval(4000);
    },
    fail(message: string) {
      wrap.textContent = `Once: ${message}`;
      wrap.style.background = "#7f1d1d";
      scheduleRemoval(6000);
    },
  };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

void (async () => {
  const w = window as Window & OnceWindow;
  if (w.__once_dispatcher_ran__) return;
  w.__once_dispatcher_ran__ = true;

  const hostname = window.location.hostname;
  const fullUrl = window.location.href;
  const portal = detectPortal(hostname, fullUrl);
  if (!portal) return;

  const filler = FILLERS[portal];
  if (!filler) return;

  const toast = mountToast();

  const profile = await loadProfile();
  if (!profile) {
    toast.fail("vault locked or no active profile");
    return;
  }

  const ctx: FillerContext = {
    hostname,
    portal,
    log: (msg, extra) => console.info(`[once.cs:${portal}] ${msg}`, extra ?? {}),
    onProgress: (r: FillReport) => {
      const total = r.filled.length + r.skipped.length;
      toast.update(r.filled.length, total);
    },
  };

  const started = performance.now();
  let report: FillReport;
  try {
    report = await filler(profile, ctx);
  } catch (err) {
    console.error("[once.cs] filler threw", err);
    toast.fail("filler error — see console");
    return;
  }
  const durationMs = Math.round(performance.now() - started);

  toast.finish(
    `filled ${report.filled.length}/${
      report.filled.length + report.skipped.length
    } fields`,
  );

  await reportToBackground({
    type: "FILL_REPORT",
    portal,
    hostname,
    url: fullUrl,
    filled: report.filled,
    skipped: report.skipped,
    durationMs,
  });
})();

// Exported for unit tests.
export const __test__ = {
  detectPortal,
  mountToast,
  HOST_RULES,
  URL_RULES,
  isContentFillMessage,
  registerFillListener,
};

registerFillListener();
