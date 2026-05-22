/**
 * Tests for background/portalDetector — URL-pattern detection.
 */
import { describe, expect, it } from "vitest";

import {
  detectFromUrl,
  htmlHash,
  PORTAL_BADGES,
  RULES,
} from "../../src/background/portalDetector";

describe("detectFromUrl", () => {
  it("detects appliedepic", () => {
    const r = detectFromUrl("https://app.appliedepic.com/login");
    expect(r?.portal).toBe("applied_epic");
    expect(r?.confidence).toBeGreaterThan(0.9);
  });

  it("detects ams360, sircon, amtrust, markel, cna, nationwide via known URLs", () => {
    expect(detectFromUrl("https://x.ams360.com/")?.portal).toBe(
      "vertafore_ams360",
    );
    expect(detectFromUrl("https://x.sircon.com/")?.portal).toBe(
      "vertafore_sircon",
    );
    expect(detectFromUrl("https://producers.amtrustfinancial.com/")?.portal).toBe(
      "amtrust",
    );
    expect(detectFromUrl("https://www.markelcorp.com/")?.portal).toBe(
      "markel",
    );
    expect(detectFromUrl("https://cnabrokerportal.cna.com/")?.portal).toBe(
      "cna",
    );
    expect(
      detectFromUrl("https://www.nationwide.com/business/quote")?.portal,
    ).toBe("nationwide_es");
  });

  it("returns null on unrelated URL", () => {
    expect(detectFromUrl("https://google.com")).toBeNull();
  });

  it("returns null on invalid URL", () => {
    expect(detectFromUrl("not-a-url")).toBeNull();
  });

  it("picks the highest-confidence rule when multiple match", () => {
    const r = detectFromUrl("https://x.markelcorp.com/producers");
    expect(r?.portal).toBe("markel");
    // markelcorp host rule (0.9) wins over the URL pattern (0.8).
    expect(r?.confidence).toBeGreaterThanOrEqual(0.9);
  });
});

describe("htmlHash", () => {
  it("is deterministic and 8 hex chars", () => {
    const a = htmlHash("hello");
    const b = htmlHash("hello");
    expect(a).toBe(b);
    expect(a).toMatch(/^[0-9a-f]{8}$/);
    expect(htmlHash("hello")).not.toBe(htmlHash("world"));
  });
});

describe("PORTAL_BADGES", () => {
  it("covers every platform referenced by RULES", () => {
    for (const r of RULES) {
      expect(PORTAL_BADGES[r.platform]).toBeDefined();
    }
  });
});
