/**
 * Filler for Applied Epic supplier / producer intake forms.
 *
 * Applied Epic is a brokerage management platform; its intake forms are
 * traditional server-rendered HTML with a few ARIA combobox widgets for
 * picklists (state, country, NAICS). All inputs are addressed by visible
 * label text so this filler survives the cosmetic re-skins Applied ships
 * a few times per year.
 */
import type { SupplierProfile } from "../../types/profile";
import {
  fillByLabel,
  setComboboxByLabel,
  type FillReport,
  type FillerContext,
} from "./_shared";

export async function fill(
  profile: SupplierProfile,
  ctx: FillerContext,
): Promise<FillReport> {
  const report: FillReport = { filled: [], skipped: [] };

  const tryFill = (label: string, value: string | undefined): void => {
    if (value === undefined || value === "") {
      report.skipped.push(label);
      return;
    }
    const ok = fillByLabel(label, value);
    if (ok) {
      report.filled.push(label);
      ctx.onProgress?.(report);
    } else {
      report.skipped.push(label);
    }
  };

  // ---- Identity --------------------------------------------------------
  tryFill("Legal Name", profile.legal_name);
  tryFill("DBA Name", profile.dba_name);
  tryFill("FEIN", profile.ein);
  tryFill("NAICS Code", profile.naics_code);
  tryFill("Website", profile.website);

  // ---- Primary contact -------------------------------------------------
  tryFill("Email", profile.primary_email);
  tryFill("Phone", profile.primary_phone);

  // ---- Address ---------------------------------------------------------
  if (profile.address) {
    tryFill("Address Line 1", profile.address.line1);
    tryFill("Address Line 2", profile.address.line2);
    tryFill("City", profile.address.city);
    tryFill("Postal Code", profile.address.postal_code);

    // Applied Epic uses a combobox for state + country.
    const stateOk = await setComboboxByLabel(
      "body",
      "State",
      profile.address.region,
    );
    (stateOk ? report.filled : report.skipped).push("State");
    if (stateOk) ctx.onProgress?.(report);

    const countryOk = await setComboboxByLabel(
      "body",
      "Country",
      profile.address.country,
    );
    (countryOk ? report.filled : report.skipped).push("Country");
    if (countryOk) ctx.onProgress?.(report);
  } else {
    report.skipped.push("Address");
  }

  // ---- Producer credential --------------------------------------------
  tryFill("NPN", profile.npn);

  ctx.log("applied_epic fill complete", {
    filled: report.filled.length,
    skipped: report.skipped.length,
  });
  return report;
}
