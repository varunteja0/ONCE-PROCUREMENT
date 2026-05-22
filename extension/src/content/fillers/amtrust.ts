/**
 * Filler for the AmTrust producer portal (`producers.amtrustfinancial.com`).
 *
 * AmTrust's producer intake is a multi-section form with:
 *   - free-text inputs for identity (legal_name, EIN, NAICS, email, phone)
 *   - a Certificate-of-Insurance block (carrier, policy #, expiry, limits)
 *   - a "Lines of Business" multi-select rendered as a checkbox grid
 */
import type { SupplierProfile } from "../../types/profile";
import {
  fillByLabel,
  setCheckboxByLabel,
  type FillReport,
  type FillerContext,
} from "./_shared";

const LOB_LABELS: Record<string, RegExp> = {
  workers_comp: /workers'?\s*comp/i,
  general_liability: /general\s+liability/i,
  professional_liability: /professional\s+liability/i,
  commercial_auto: /commercial\s+auto/i,
  cyber: /cyber/i,
  property: /\bproperty\b/i,
  umbrella: /umbrella/i,
};

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
  tryFill(/legal\s*name|business\s*name/i, profile.legal_name);
  tryFill(/(fein|ein|tax\s*id)/i, profile.ein);
  tryFill(/naics/i, profile.naics_code);
  tryFill(/email/i, profile.primary_email);
  tryFill(/phone/i, profile.primary_phone);

  // ---- COI -------------------------------------------------------------
  if (profile.coi) {
    tryFill(/coi\s*carrier|insurance\s*carrier/i, profile.coi.carrier);
    tryFill(/policy\s*(number|#)/i, profile.coi.policy_number);
    tryFill(/(coi\s*)?expiration|expiry/i, profile.coi.expiry);
    tryFill(
      /each\s*occurrence|per\s*occurrence/i,
      String(profile.coi.limit_each_occurrence),
    );
    tryFill(/aggregate/i, String(profile.coi.limit_aggregate));
  } else {
    report.skipped.push("coi");
  }

  // ---- Lines of Business (checkbox grid) ------------------------------
  const selected = new Set(profile.lines_of_business ?? []);
  for (const [key, pattern] of Object.entries(LOB_LABELS)) {
    const want = selected.has(key);
    if (!want) continue;
    if (setCheckboxByLabel(pattern, true)) {
      report.filled.push(`lob:${key}`);
      ctx.onProgress?.(report);
    } else {
      report.skipped.push(`lob:${key}`);
    }
  }

  ctx.log("amtrust fill complete", {
    filled: report.filled.length,
    skipped: report.skipped.length,
  });
  return report;
}
