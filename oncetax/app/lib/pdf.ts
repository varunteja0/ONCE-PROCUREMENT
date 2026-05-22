import { PDFDocument, StandardFonts, rgb } from "pdf-lib";

import { getStateRate, type SupportedState } from "./tax_calc";

export interface FilingPrepInput {
  shop: string;
  state: SupportedState;
  period_start: string;
  period_end: string;
  gross_sales_cents: number;
  taxable_cents: number;
  tax_due_cents: number;
}

function fmtUsd(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

export async function buildFilingPrepPdf(
  input: FilingPrepInput,
): Promise<Uint8Array> {
  const pdf = await PDFDocument.create();
  const page = pdf.addPage([612, 792]); // US Letter
  const font = await pdf.embedFont(StandardFonts.Helvetica);
  const bold = await pdf.embedFont(StandardFonts.HelveticaBold);

  const ink = rgb(0.05, 0.05, 0.1);
  const muted = rgb(0.35, 0.35, 0.4);
  const accent = rgb(0.06, 0.46, 0.43);

  let y = 740;

  page.drawText("OnceTax — Sales Tax Filing Prep Worksheet", {
    x: 50,
    y,
    size: 18,
    font: bold,
    color: ink,
  });
  y -= 26;
  page.drawText("v0 — state-level base rate only. Local rates NOT included.", {
    x: 50,
    y,
    size: 9,
    font,
    color: muted,
  });
  y -= 30;

  page.drawText(`State: ${input.state}`, { x: 50, y, size: 14, font: bold, color: accent });
  y -= 18;
  page.drawText(`Shop: ${input.shop}`, { x: 50, y, size: 11, font, color: ink });
  y -= 14;
  page.drawText(
    `Period: ${input.period_start} → ${input.period_end}`,
    { x: 50, y, size: 11, font, color: ink },
  );
  y -= 30;

  const rate = getStateRate(input.state);
  const rows: [string, string][] = [
    ["Gross sales", fmtUsd(input.gross_sales_cents)],
    ["Taxable sales", fmtUsd(input.taxable_cents)],
    ["State base rate", `${(rate.state_base_rate * 100).toFixed(4)}%`],
    ["Tax due (state portion only)", fmtUsd(input.tax_due_cents)],
    ["Deductions / adjustments", "[ placeholder — fill manually ]"],
  ];

  for (const [label, value] of rows) {
    page.drawText(label, { x: 50, y, size: 11, font, color: ink });
    page.drawText(value, { x: 360, y, size: 11, font: bold, color: ink });
    y -= 18;
  }

  y -= 20;
  const disclaimer = [
    "This worksheet is a filing-prep aid only. OnceTax does NOT auto-submit to",
    "state portals in v0. You are responsible for filing with the state.",
    "",
    `Notes: ${rate.notes}`,
  ];
  for (const line of disclaimer) {
    page.drawText(line, { x: 50, y, size: 9, font, color: muted });
    y -= 12;
  }

  page.drawText(`Generated ${new Date().toISOString()}`, {
    x: 50,
    y: 40,
    size: 8,
    font,
    color: muted,
  });

  return pdf.save();
}
