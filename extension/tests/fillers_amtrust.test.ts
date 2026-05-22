/**
 * @vitest-environment jsdom
 *
 * Unit tests for the AmTrust producer-portal filler.
 *
 * Builds a synthetic form with the expected AmTrust labels (identity,
 * COI, lines-of-business checkbox grid), invokes `fill(profile, ctx)`
 * and asserts every field value was set AND that the canonical
 * `input` + `change` events fired (tracked via event-listener spies
 * attached during DOM construction).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fill } from "../src/content/fillers/amtrust";
import type { FillerContext } from "../src/content/fillers/_shared";
import type { SupplierProfile } from "../src/types/profile";

interface EventSpy {
  input: ReturnType<typeof vi.fn>;
  change: ReturnType<typeof vi.fn>;
}

const eventSpies = new Map<string, EventSpy>();

function makeField(
  kind: "input" | "textarea",
  labelText: string,
  id: string,
  attrs: Record<string, string> = {},
): HTMLLabelElement {
  const wrap = document.createElement("label");
  wrap.setAttribute("for", id);
  wrap.textContent = labelText;

  const el =
    kind === "input"
      ? document.createElement("input")
      : document.createElement("textarea");
  el.id = id;
  el.setAttribute("name", id);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);

  const spy: EventSpy = { input: vi.fn(), change: vi.fn() };
  el.addEventListener("input", spy.input);
  el.addEventListener("change", spy.change);
  eventSpies.set(id, spy);

  wrap.appendChild(el);
  return wrap;
}

function makeCheckbox(labelText: string, id: string): HTMLLabelElement {
  const wrap = document.createElement("label");
  wrap.setAttribute("for", id);
  wrap.textContent = labelText;

  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.id = id;
  cb.setAttribute("name", id);

  const spy: EventSpy = { input: vi.fn(), change: vi.fn() };
  cb.addEventListener("input", spy.input);
  cb.addEventListener("change", spy.change);
  eventSpies.set(id, spy);

  wrap.appendChild(cb);
  return wrap;
}

function buildAmTrustForm(): void {
  const form = document.createElement("form");

  // Identity
  form.appendChild(makeField("input", "Legal Name", "legal_name"));
  form.appendChild(makeField("input", "FEIN", "ein"));
  form.appendChild(makeField("input", "NAICS", "naics"));
  form.appendChild(makeField("input", "Email", "email"));
  form.appendChild(makeField("input", "Phone", "phone"));

  // COI
  form.appendChild(makeField("input", "Insurance Carrier", "coi_carrier"));
  form.appendChild(makeField("input", "Policy Number", "policy_number"));
  form.appendChild(makeField("input", "Expiration", "expiry"));
  form.appendChild(makeField("input", "Each Occurrence", "each_occ"));
  form.appendChild(makeField("input", "Aggregate", "aggregate"));

  // LOB checkboxes
  form.appendChild(makeCheckbox("Workers' Comp", "lob_wc"));
  form.appendChild(makeCheckbox("General Liability", "lob_gl"));
  form.appendChild(makeCheckbox("Professional Liability", "lob_pl"));
  form.appendChild(makeCheckbox("Commercial Auto", "lob_auto"));
  form.appendChild(makeCheckbox("Cyber", "lob_cyber"));
  form.appendChild(makeCheckbox("Property", "lob_property"));
  form.appendChild(makeCheckbox("Umbrella", "lob_umbrella"));

  document.body.appendChild(form);
}

function profile(): SupplierProfile {
  return {
    legal_name: "Acme Insurance Brokers LLC",
    ein: "12-3456789",
    naics_code: "524210",
    primary_email: "ops@acme.example",
    primary_phone: "+1-415-555-0142",
    coi: {
      carrier: "Hartford",
      policy_number: "POL-9001",
      expiry: "2026-01-01",
      limit_each_occurrence: 1_000_000,
      limit_aggregate: 2_000_000,
    },
    lines_of_business: ["workers_comp", "general_liability", "cyber"],
  };
}

function getInput(id: string): HTMLInputElement {
  const el = document.getElementById(id);
  if (!(el instanceof HTMLInputElement)) {
    throw new Error(`expected input#${id}`);
  }
  return el;
}

function ctx(): FillerContext {
  return {
    hostname: "producers.amtrustfinancial.com",
    portal: "amtrust",
    log: vi.fn(),
  };
}

beforeEach(() => {
  document.body.innerHTML = "";
  eventSpies.clear();
  buildAmTrustForm();
});

afterEach(() => {
  document.body.innerHTML = "";
  eventSpies.clear();
});

describe("amtrust filler", () => {
  it("sets every text field and fires input + change events", async () => {
    const p = profile();
    const report = await fill(p, ctx());

    expect(getInput("legal_name").value).toBe(p.legal_name);
    expect(getInput("ein").value).toBe(p.ein);
    expect(getInput("naics").value).toBe(p.naics_code);
    expect(getInput("email").value).toBe(p.primary_email);
    expect(getInput("phone").value).toBe(p.primary_phone);

    expect(getInput("coi_carrier").value).toBe(p.coi!.carrier);
    expect(getInput("policy_number").value).toBe(p.coi!.policy_number);
    expect(getInput("expiry").value).toBe(p.coi!.expiry);
    expect(getInput("each_occ").value).toBe(
      String(p.coi!.limit_each_occurrence),
    );
    expect(getInput("aggregate").value).toBe(String(p.coi!.limit_aggregate));

    const textIds = [
      "legal_name",
      "ein",
      "naics",
      "email",
      "phone",
      "coi_carrier",
      "policy_number",
      "expiry",
      "each_occ",
      "aggregate",
    ];
    for (const id of textIds) {
      const spy = eventSpies.get(id);
      expect(spy, `spies for #${id}`).toBeDefined();
      expect(spy!.input.mock.calls.length).toBeGreaterThanOrEqual(1);
      expect(spy!.change.mock.calls.length).toBeGreaterThanOrEqual(1);
    }

    expect(report.skipped).not.toContain("coi");
    expect(report.filled.length).toBeGreaterThan(0);
  });

  it("toggles only the requested LOB checkboxes and fires change events", async () => {
    await fill(profile(), ctx());

    expect(getInput("lob_wc").checked).toBe(true);
    expect(getInput("lob_gl").checked).toBe(true);
    expect(getInput("lob_cyber").checked).toBe(true);

    expect(getInput("lob_pl").checked).toBe(false);
    expect(getInput("lob_auto").checked).toBe(false);
    expect(getInput("lob_property").checked).toBe(false);
    expect(getInput("lob_umbrella").checked).toBe(false);

    for (const id of ["lob_wc", "lob_gl", "lob_cyber"]) {
      const spy = eventSpies.get(id);
      expect(spy, `spies for #${id}`).toBeDefined();
      expect(spy!.change.mock.calls.length).toBeGreaterThanOrEqual(1);
    }

    for (const id of ["lob_pl", "lob_auto", "lob_property", "lob_umbrella"]) {
      const spy = eventSpies.get(id);
      expect(spy!.change).not.toHaveBeenCalled();
    }
  });

  it("calls ctx.log on completion with filled/skipped totals", async () => {
    const c = ctx();
    await fill(profile(), c);
    expect(c.log).toHaveBeenCalledWith(
      "amtrust fill complete",
      expect.objectContaining({
        filled: expect.any(Number),
        skipped: expect.any(Number),
      }),
    );
  });
});
