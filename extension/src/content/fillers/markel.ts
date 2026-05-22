/**
 * Filler for the Markel producer portal (`*.markelcorp.com` and
 * `markel.com/producers`).
 *
 * Markel's intake form mixes plain inputs with ARIA comboboxes for state
 * and for the producer's primary line of business. License-state is a
 * multi-select checkbox grid (one box per US state abbreviation).
 */
import type { SupplierProfile } from "../../types/profile";
import {
  fillByLabel,
  setCheckboxByLabel,
  setComboboxByLabel,
  type FillReport,
  type FillerContext,
} from "./_shared";

export async function fill(
  profile: SupplierProfile,
  ctx: FillerContext,
): Promise<FillReport> {
  const report: FillReport = { filled: [], skipped: [] };

  const tryFill = (label: string | RegExp, value: string | undefined): void => {
    const key = typeof label === "string" ? label : label.source;
    if (value === undefined || value === "") {
      report.skipped.push(key);
      return;
    }
    if (fillByLabel(label, value)) {
      report.filled.push(key);
      ctx.onProgress?.(report);
    } else {
      report.skipped.push(key);
    }
  };

  // ---- Identity --------------------------------------------------------
  tryFill(/legal\s*name|agency\s*name/i, profile.legal_name);
  tryFill(/dba/i, profile.dba_name);
  tryFill(/(fein|ein|tax\s*id)/i, profile.ein);
  tryFill(/naics/i, profile.naics_code);
  tryFill(/website/i, profile.website);
  tryFill(/npn/i, profile.npn);

  // ---- Contact ---------------------------------------------------------
  tryFill(/email/i, profile.primary_email);
  tryFill(/phone/i, profile.primary_phone);

  // ---- Address ---------------------------------------------------------
  if (profile.address) {
    tryFill(/address\s*(line\s*)?1|street/i, profile.address.line1);
    tryFill(/address\s*(line\s*)?2|suite|apt/i, profile.address.line2);
    tryFill(/city/i, profile.address.city);
    tryFill(/(zip|postal)\s*code/i, profile.address.postal_code);

    const stateOk = await setComboboxByLabel(
      "body",
      "State",
      profile.address.region,
    );
    (stateOk ? report.filled : report.skipped).push("State");
    if (stateOk) ctx.onProgress?.(report);
  } else {
    report.skipped.push("Address");
  }

  // ---- COI -------------------------------------------------------------
  if (profile.coi) {
    tryFill(/coi\s*carrier|insurance\s*carrier/i, profile.coi.carrier);
    tryFill(/policy\s*(number|#)/i, profile.coi.policy_number);
    tryFill(/(coi\s*)?expiration|expiry/i, profile.coi.expiry);
  }

  // ---- License states (one checkbox per state code) -------------------
  for (const state of profile.license_states ?? []) {
    if (state.length === 0) continue;
    // Match either the bare two-letter code as a word, or the state label.
    const pattern = new RegExp(`\\b${escapeRegex(state)}\\b`, "i");
    if (setCheckboxByLabel(pattern, true)) {
      report.filled.push(`license:${state}`);
      ctx.onProgress?.(report);
    } else {
      report.skipped.push(`license:${state}`);
    }
  }

  ctx.log("markel fill complete", {
    filled: report.filled.length,
    skipped: report.skipped.length,
  });
  return report;
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
