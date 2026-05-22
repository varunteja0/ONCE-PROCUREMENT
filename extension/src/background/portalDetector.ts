/**
 * URL-pattern based portal detector — runs in the background service
 * worker (no DOM). Mirrors the content-script-side rules in
 * `content/dispatcher.ts` and the backend's `automation/detector.py`.
 */

import type { PortalPlatform } from "../types/portal";

export interface DetectorRule {
  pattern: RegExp;
  /** Matched against full URL when `kind === 'url'`, hostname otherwise. */
  kind: "host" | "url";
  platform: PortalPlatform;
  /** 0..1 — base confidence before any DOM-side boosts. */
  baseConfidence: number;
}

export const RULES: readonly DetectorRule[] = [
  { pattern: /(^|\.)appliedepic\.com$/i, kind: "host", platform: "applied_epic", baseConfidence: 0.95 },
  { pattern: /(^|\.)ams360\.com$/i, kind: "host", platform: "vertafore_ams360", baseConfidence: 0.95 },
  { pattern: /(^|\.)sircon\.com$/i, kind: "host", platform: "vertafore_sircon", baseConfidence: 0.95 },
  { pattern: /(^|\.)amtrustfinancial\.com$/i, kind: "host", platform: "amtrust", baseConfidence: 0.95 },
  { pattern: /^producers\.amtrust/i, kind: "host", platform: "amtrust", baseConfidence: 0.9 },
  { pattern: /(^|\.)markelcorp\.com$/i, kind: "host", platform: "markel", baseConfidence: 0.9 },
  { pattern: /(^|\.)markel\.com$/i, kind: "host", platform: "markel", baseConfidence: 0.6 },
  { pattern: /(^|\.)cna\.com$/i, kind: "host", platform: "cna", baseConfidence: 0.9 },
  { pattern: /^cnabrokerportal\.cna\.com$/i, kind: "host", platform: "cna", baseConfidence: 0.95 },
  { pattern: /markel\.com\/producers/i, kind: "url", platform: "markel", baseConfidence: 0.8 },
  { pattern: /nationwide\.com\/business/i, kind: "url", platform: "nationwide_es", baseConfidence: 0.8 },
] as const;

export interface DetectorResult {
  portal: PortalPlatform;
  confidence: number;
}

export function detectFromUrl(rawUrl: string): DetectorResult | null {
  let url: URL;
  try {
    url = new URL(rawUrl);
  } catch {
    return null;
  }
  const host = url.hostname;
  const full = url.href;

  let best: DetectorResult | null = null;
  for (const r of RULES) {
    const text = r.kind === "host" ? host : full;
    if (r.pattern.test(text)) {
      const candidate: DetectorResult = {
        portal: r.platform,
        confidence: r.baseConfidence,
      };
      if (!best || candidate.confidence > best.confidence) best = candidate;
    }
  }
  return best;
}

/** Cheap FNV-1a 32-bit hash used to de-duplicate detections. */
export function htmlHash(input: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < input.length; i += 1) {
    h ^= input.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h.toString(16).padStart(8, "0");
}

export const PORTAL_BADGES: Record<PortalPlatform, { text: string; color: string }> = {
  applied_epic: { text: "EPIC", color: "#0ea5e9" },
  vertafore_ams360: { text: "AMS", color: "#0ea5e9" },
  vertafore_sircon: { text: "SIR", color: "#0ea5e9" },
  amtrust: { text: "AMT", color: "#10b981" },
  markel: { text: "MKL", color: "#a855f7" },
  nationwide_es: { text: "NW", color: "#0f766e" },
  cna: { text: "CNA", color: "#dc2626" },
  guidewire: { text: "GW", color: "#475569" },
  hawksoft: { text: "HWK", color: "#475569" },
  ezlynx: { text: "EZ", color: "#475569" },
  nowcerts: { text: "NOW", color: "#475569" },
};
