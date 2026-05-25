/**
 * Content-script entry point. Runs once per page load (idempotent), detects
 * the carrier portal from `window.location.hostname`, loads the active
 * supplier profile from the background service-worker / vault, invokes the
 * matching filler, and surfaces an in-page toast plus a `FILL_REPORT`
 * message back to the background for telemetry.
 */
import { send } from "../lib/messaging";
import type { PortalPlatform } from "../types/portal";
import type { SupplierProfile } from "../types/profile";
import type { FillerContext, FillerFn } from "./fillers/_shared";
import * as amtrust from "./fillers/amtrust";
import * as appliedEpic from "./fillers/applied_epic";
import * as markel from "./fillers/markel";

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
  if (typeof chrome === "undefined" || !chrome.runtime || !chrome.runtime.onMessage) {
    return;
  }
  chrome.runtime.onMessage.addListener(
    (
      message: unknown,
      _sender: chrome.runtime.MessageSender,
      sendResponse: (response: ContentFillResponse) => void,
    ): boolean => {
      // Defense-in-depth: reject messages from any sender other than this
      // extension. MV3 already blocks externally_connectable by default,
      // but if that's ever loosened we don't want the content script to
      // honour fill commands from arbitrary origins.
      if (_sender.id !== chrome.runtime.id) return false;
      if (!isContentFillMessage(message)) return false;
      const filler = FILLERS[message.portal];
      if (!filler) {
        sendResponse({ ok: false, error: `no_filler:${message.portal}` });
        return false;
      }
      const ctx: FillerContext = {
        hostname: window.location.hostname,
        portal: message.portal,
        log: () => undefined,
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

  await send({
    type: "portal.detect",
    detection: {
      portal,
      hostname,
      url: fullUrl,
      confidence: 0.9,
      html_hash: `${document.documentElement?.innerHTML.length ?? 0}:${document.title}`,
    },
  }).catch(() => undefined);
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
