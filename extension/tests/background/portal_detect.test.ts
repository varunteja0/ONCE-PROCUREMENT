/**
 * Regression test for the "portal.detect" background handler. The
 * previous implementation keyed the detection cache by
 * `m.detection.url.length` instead of `sender.tab.id`, so subsequent
 * "portal.active" lookups (which the popup makes by tabId) silently
 * missed.
 */
import { beforeEach, describe, expect, it } from "vitest";

import { __test__ } from "../../src/background/index";
import type { PortalDetection } from "../../src/lib/messaging";

const { handlers, detectionByTab } = __test__;

function detection(): PortalDetection {
  return {
    portal: "applied_epic",
    hostname: "app.appliedepic.com",
    url: "https://app.appliedepic.com/intake",
    confidence: 0.95,
    html_hash: "abcd1234",
  };
}

beforeEach(() => {
  detectionByTab.clear();
});

describe("background portal.detect handler", () => {
  it("keys the detection cache by sender.tab.id", async () => {
    const resp = await handlers["portal.detect"]!({ type: "portal.detect", detection: detection() }, {
      tab: { id: 42 },
    } as chrome.runtime.MessageSender);
    expect(resp).toEqual({ ok: true, stored: true });
    expect(detectionByTab.get(42)?.portal).toBe("applied_epic");

    const active = await handlers["portal.active"]!(
      { type: "portal.active", tabId: 42 },
      {} as chrome.runtime.MessageSender,
    );
    expect(active.ok).toBe(true);
    if (active.ok) expect(active.detection?.portal).toBe("applied_epic");
  });

  it("returns stored=false when the sender has no tab id", async () => {
    const resp = await handlers["portal.detect"]!(
      { type: "portal.detect", detection: detection() },
      {} as chrome.runtime.MessageSender,
    );
    expect(resp).toEqual({ ok: true, stored: false });
    expect(detectionByTab.size).toBe(0);
  });
});
