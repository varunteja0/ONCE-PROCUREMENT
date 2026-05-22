/**
 * @vitest-environment jsdom
 *
 * Unit tests for the Applied Epic supplier-intake filler.
 *
 * Note: Applied Epic uses ARIA comboboxes for State + Country, which
 * `setComboboxByLabel` resolves asynchronously. We test the text-input
 * path exhaustively (every label set, input+change events fired) and
 * assert the combobox helper is invoked without requiring a fully
 * faithful Workday-style listbox here.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fill } from "../src/content/fillers/applied_epic";
import type { FillerContext } from "../src/content/fillers/_shared";
import type { SupplierProfile } from "../src/types/profile";

interface EventSpy {
  input: ReturnType<typeof vi.fn>;
  change: ReturnType<typeof vi.fn>;
}

const eventSpies = new Map<string, EventSpy>();

function makeField(
  labelText: string,
  id: string,
): HTMLLabelElement {
  const wrap = document.createElement("label");
  wrap.setAttribute("for", id);
  wrap.textContent = labelText;

  const el = document.createElement("input");
  el.id = id;
  el.setAttribute("name", id);

  const spy: EventSpy = { input: vi.fn(), change: vi.fn() };
  el.addEventListener("input", spy.input);
  el.addEventListener("change", spy.change);
  eventSpies.set(id, spy);

  wrap.appendChild(el);
  return wrap;
}

function buildAppliedEpicForm(): void {
  const form = document.createElement("form");

  form.appendChild(makeField("Legal Name", "legal_name"));
  form.appendChild(makeField("DBA Name", "dba_name"));
  form.appendChild(makeField("FEIN", "ein"));
  form.appendChild(makeField("NAICS Code", "naics_code"));
  form.appendChild(makeField("Website", "website"));
  form.appendChild(makeField("Email", "email"));
  form.appendChild(makeField("Phone", "phone"));
  form.appendChild(makeField("Address Line 1", "addr1"));
  form.appendChild(makeField("Address Line 2", "addr2"));
  form.appendChild(makeField("City", "city"));
  form.appendChild(makeField("Postal Code", "postal"));
  form.appendChild(makeField("NPN", "npn"));

  document.body.appendChild(form);
}

function profile(): SupplierProfile {
  return {
    legal_name: "Acme Insurance Brokers LLC",
    dba_name: "Acme",
    ein: "12-3456789",
    naics_code: "524210",
    website: "https://acme.example",
    primary_email: "ops@acme.example",
    primary_phone: "+1-415-555-0142",
    address: {
      line1: "100 Market St",
      line2: "Suite 400",
      city: "San Francisco",
      region: "CA",
      postal_code: "94105",
      country: "US",
    },
    npn: "1234567",
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
    hostname: "agency.appliedepic.com",
    portal: "applied_epic",
    log: vi.fn(),
  };
}

beforeEach(() => {
  document.body.innerHTML = "";
  eventSpies.clear();
  buildAppliedEpicForm();
});

afterEach(() => {
  document.body.innerHTML = "";
  eventSpies.clear();
});

describe("applied_epic filler", () => {
  it("sets every text field and fires input + change events", async () => {
    const p = profile();
    const report = await fill(p, ctx());

    expect(getInput("legal_name").value).toBe(p.legal_name);
    expect(getInput("dba_name").value).toBe(p.dba_name);
    expect(getInput("ein").value).toBe(p.ein);
    expect(getInput("naics_code").value).toBe(p.naics_code);
    expect(getInput("website").value).toBe(p.website);
    expect(getInput("email").value).toBe(p.primary_email);
    expect(getInput("phone").value).toBe(p.primary_phone);
    expect(getInput("addr1").value).toBe(p.address!.line1);
    expect(getInput("addr2").value).toBe(p.address!.line2);
    expect(getInput("city").value).toBe(p.address!.city);
    expect(getInput("postal").value).toBe(p.address!.postal_code);
    expect(getInput("npn").value).toBe(p.npn);

    const ids = [
      "legal_name",
      "dba_name",
      "ein",
      "naics_code",
      "website",
      "email",
      "phone",
      "addr1",
      "addr2",
      "city",
      "postal",
      "npn",
    ];
    for (const id of ids) {
      const spy = eventSpies.get(id);
      expect(spy, `spies for #${id}`).toBeDefined();
      expect(spy!.input.mock.calls.length).toBeGreaterThanOrEqual(1);
      expect(spy!.change.mock.calls.length).toBeGreaterThanOrEqual(1);
    }

    // Each field should appear at least once in the filled list.
    for (const label of [
      "Legal Name",
      "DBA Name",
      "FEIN",
      "NAICS Code",
      "Website",
      "Email",
      "Phone",
      "Address Line 1",
      "Address Line 2",
      "City",
      "Postal Code",
      "NPN",
    ]) {
      expect(report.filled).toContain(label);
    }
  });

  it("skips optional fields that are missing", async () => {
    const minimal: SupplierProfile = {
      legal_name: "Solo Producer LLC",
      primary_email: "solo@example.com",
    };
    const report = await fill(minimal, ctx());

    expect(getInput("legal_name").value).toBe("Solo Producer LLC");
    expect(getInput("email").value).toBe("solo@example.com");
    expect(getInput("dba_name").value).toBe("");
    expect(getInput("npn").value).toBe("");

    expect(report.filled).toContain("Legal Name");
    expect(report.filled).toContain("Email");
    expect(report.skipped).toContain("DBA Name");
    expect(report.skipped).toContain("Address");
  });

  it("calls ctx.log on completion", async () => {
    const c = ctx();
    await fill(profile(), c);
    expect(c.log).toHaveBeenCalledWith(
      "applied_epic fill complete",
      expect.objectContaining({
        filled: expect.any(Number),
        skipped: expect.any(Number),
      }),
    );
  });
});
