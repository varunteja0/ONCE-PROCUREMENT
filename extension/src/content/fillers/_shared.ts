/**
 * Shared DOM-fill helpers used by every portal-specific filler.
 *
 * TypeScript port of autoapplyai's `_shared.ts` (notably the
 * `setWorkdayCombobox` helper and the React tracked-input native-setter
 * trick required to defeat React's onChange synthetic event de-duping).
 *
 * No `any`. Every helper is defensive about the DOM (the page can mutate
 * underneath us) and uses small `sleep` / `waitFor` retries instead of
 * `MutationObserver` so the helpers are easy to unit-test under jsdom.
 */
import type { SupplierProfile } from "../../types/profile";
// SupplierProfile is re-exported only for the per-portal fillers' type imports.
export type { SupplierProfile };

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

export interface FillReport {
  filled: string[];
  skipped: string[];
}

export interface FillerContext {
  /** Plain hostname (no scheme, no port) — `window.location.hostname`. */
  hostname: string;
  /** Logical portal identifier (matches `PortalPlatform`). */
  portal: string;
  /** Per-page logger; defaults to `console`. */
  log: (msg: string, extra?: Record<string, unknown>) => void;
  /** Callback fired after each successful field fill (for UI progress). */
  onProgress?: (report: FillReport) => void;
}

export type FillerFn = (
  profile: SupplierProfile,
  ctx: FillerContext,
) => Promise<FillReport>;

// ---------------------------------------------------------------------------
// Timing primitives
// ---------------------------------------------------------------------------

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export interface WaitForOptions {
  /** Total wall-clock budget in milliseconds. Defaults to 1500 ms. */
  timeoutMs?: number;
  /** Poll interval in milliseconds. Defaults to 40 ms. */
  intervalMs?: number;
}

/**
 * Poll `predicate` every `intervalMs` until it returns a truthy value or the
 * `timeoutMs` budget is exhausted. Returns the resolved value, or `null` on
 * timeout. Never throws.
 */
export async function waitFor<T>(
  predicate: () => T | null | undefined,
  opts: WaitForOptions = {},
): Promise<T | null> {
  const timeoutMs = opts.timeoutMs ?? 1500;
  const intervalMs = opts.intervalMs ?? 40;
  const deadline = Date.now() + timeoutMs;
  // First synchronous attempt — common case where the node already exists.
  const first = safeCall(predicate);
  if (first) return first;
  while (Date.now() < deadline) {
    await sleep(intervalMs);
    const v = safeCall(predicate);
    if (v) return v;
  }
  return null;
}

function safeCall<T>(fn: () => T | null | undefined): T | null {
  try {
    const v = fn();
    return v ?? null;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// React tracked-input setter trick
// ---------------------------------------------------------------------------

/**
 * Sets the value of a React-controlled `<input>` / `<textarea>` such that
 * React notices the change. React installs a value-tracker on inputs that
 * short-circuits subsequent assignments; we sidestep it by invoking the
 * *native* setter from the prototype, then dispatching `input` + `change`.
 *
 * Mirrors autoapplyai's `setReactTrackedInput`.
 */
export function setReactTrackedInput(
  el: HTMLInputElement | HTMLTextAreaElement,
  value: string,
): void {
  const proto =
    el instanceof HTMLTextAreaElement
      ? window.HTMLTextAreaElement.prototype
      : window.HTMLInputElement.prototype;
  const descriptor = Object.getOwnPropertyDescriptor(proto, "value");
  const setter = descriptor?.set;
  if (typeof setter === "function") {
    setter.call(el, value);
  } else {
    // Should never happen in a real browser, but keep a defensive fallback.
    el.value = value;
  }
  el.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
  el.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
}

/** Native-setter equivalent for `<select>` elements. */
export function setReactSelect(el: HTMLSelectElement, value: string): void {
  const descriptor = Object.getOwnPropertyDescriptor(
    window.HTMLSelectElement.prototype,
    "value",
  );
  const setter = descriptor?.set;
  if (typeof setter === "function") {
    setter.call(el, value);
  } else {
    el.value = value;
  }
  el.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
  el.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
}

/**
 * Fire the canonical focus/input/change/blur sequence that most "dirty"
 * form-validation frameworks expect after an external value change.
 */
export function dispatchAfterFill(
  el: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement,
): void {
  el.dispatchEvent(new FocusEvent("focus", { bubbles: true }));
  el.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
  el.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
  el.dispatchEvent(new FocusEvent("blur", { bubbles: true }));
}

// ---------------------------------------------------------------------------
// Label → field resolution
// ---------------------------------------------------------------------------

type LabelMatcher = string | RegExp;

function normalize(s: string): string {
  return s.replace(/\s+/g, " ").trim().toLowerCase();
}

function matches(text: string | null | undefined, label: LabelMatcher): boolean {
  if (!text) return false;
  const t = normalize(text);
  if (typeof label === "string") {
    const target = normalize(label);
    return t === target || t.includes(target);
  }
  return label.test(text);
}

/**
 * Locate an input/textarea/select within `scope` (default: document) whose
 * accessible label matches `label`. Checks, in order:
 *   1. `<label for="id">` linked to the field's `id`
 *   2. `aria-label` on the field
 *   3. `aria-labelledby` → referenced element's text
 *   4. `placeholder`
 *   5. `name` attribute
 *   6. Nearest preceding text node (best-effort fallback for unlabelled rows)
 */
export function findFieldByLabel(
  label: LabelMatcher,
  scope: Element | Document = document,
): HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement | null {
  const root: Document | Element = scope;
  const fields = Array.from(
    root.querySelectorAll<
      HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
    >("input, textarea, select"),
  );

  // 1. <label for=id>
  const docRoot: Document =
    scope instanceof Document ? scope : scope.ownerDocument ?? document;
  const labels = Array.from(docRoot.querySelectorAll<HTMLLabelElement>("label"));
  for (const lab of labels) {
    if (!matches(lab.textContent, label)) continue;
    const forId = lab.getAttribute("for");
    if (forId) {
      const el = docRoot.getElementById(forId);
      if (el && isFillable(el)) return el;
    }
    // Implicit label wrapping
    const nested = lab.querySelector<
      HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
    >("input, textarea, select");
    if (nested) return nested;
  }

  // 2 + 3. aria-label / aria-labelledby / 4. placeholder / 5. name
  for (const el of fields) {
    const aria = el.getAttribute("aria-label");
    if (matches(aria, label)) return el;

    const labelledBy = el.getAttribute("aria-labelledby");
    if (labelledBy) {
      const ids = labelledBy.split(/\s+/).filter(Boolean);
      const txt = ids
        .map((id) => docRoot.getElementById(id)?.textContent ?? "")
        .join(" ");
      if (matches(txt, label)) return el;
    }

    if (
      (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) &&
      matches(el.placeholder, label)
    ) {
      return el;
    }
    if (matches(el.getAttribute("name"), label)) return el;
  }

  // 6. Nearest preceding text node fallback.
  for (const el of fields) {
    const text = nearestPrecedingText(el);
    if (matches(text, label)) return el;
  }

  return null;
}

function isFillable(
  el: Element,
): el is HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement {
  return (
    el instanceof HTMLInputElement ||
    el instanceof HTMLTextAreaElement ||
    el instanceof HTMLSelectElement
  );
}

function nearestPrecedingText(el: Element): string | null {
  // Walk previous siblings then up the parent chain looking for the closest
  // text-bearing node. Bounded to ~6 hops to avoid pathological pages.
  let node: Node | null = el;
  for (let hops = 0; hops < 6 && node; hops++) {
    let prev: Node | null = node.previousSibling;
    while (prev) {
      const t = prev.textContent?.trim();
      if (t && t.length > 0 && t.length < 200) return t;
      prev = prev.previousSibling;
    }
    node = node.parentNode;
  }
  return null;
}

// ---------------------------------------------------------------------------
// ARIA combobox helper (Workday / Lightning / Material-style)
// ---------------------------------------------------------------------------

/**
 * Fill an ARIA combobox identified by its visible label.
 *
 * Steps (each step retries up to ~1500ms with `sleep(40)` between attempts):
 *   1. Find a `[role=combobox]` near a matching label.
 *   2. Click the combobox to open the listbox.
 *   3. Wait for `[role=listbox]` to appear.
 *   4. Type `value` into the combobox to filter options.
 *   5. ArrowDown to highlight the first/matching option, Enter to commit.
 *
 * Returns `true` on success, `false` if any step times out.
 */
export async function setComboboxByLabel(
  rootSelector: string,
  labelText: string,
  value: string,
): Promise<boolean> {
  const root = document.querySelector(rootSelector);
  if (!root) return false;

  const combo = await waitFor<HTMLElement>(() =>
    findComboboxByLabel(root, labelText),
  );
  if (!combo) return false;

  combo.scrollIntoView({ block: "center" });
  combo.focus();
  combo.click();

  const listbox = await waitFor<HTMLElement>(() =>
    document.querySelector<HTMLElement>("[role=listbox]"),
  );
  if (!listbox) return false;

  // Type the value to filter. Combobox may be the input itself, or wrap one.
  const typeable =
    combo instanceof HTMLInputElement
      ? combo
      : combo.querySelector<HTMLInputElement>("input");
  if (typeable) {
    setReactTrackedInput(typeable, value);
    typeable.dispatchEvent(
      new KeyboardEvent("keydown", { key: value.slice(-1), bubbles: true }),
    );
  }

  // Wait for an option matching the value, then keyboard-select it.
  const matched = await waitFor<HTMLElement>(() => {
    const opts = Array.from(
      listbox.querySelectorAll<HTMLElement>("[role=option]"),
    );
    return (
      opts.find((o) => matches(o.textContent, value)) ?? opts[0] ?? null
    );
  });
  if (!matched) return false;

  const target = typeable ?? combo;
  target.dispatchEvent(
    new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }),
  );
  await sleep(20);
  target.dispatchEvent(
    new KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
  );
  // Fallback: click the matched option directly in case key events are ignored.
  matched.click();
  return true;
}

function findComboboxByLabel(
  root: Element,
  labelText: string,
): HTMLElement | null {
  const combos = Array.from(
    root.querySelectorAll<HTMLElement>("[role=combobox]"),
  );
  // First pass: aria-label / aria-labelledby on the combobox itself.
  for (const c of combos) {
    if (matches(c.getAttribute("aria-label"), labelText)) return c;
    const lb = c.getAttribute("aria-labelledby");
    if (lb) {
      const txt = lb
        .split(/\s+/)
        .map((id) => document.getElementById(id)?.textContent ?? "")
        .join(" ");
      if (matches(txt, labelText)) return c;
    }
  }
  // Second pass: nearest preceding/sibling <label> text.
  for (const c of combos) {
    const txt = nearestPrecedingText(c);
    if (matches(txt, labelText)) return c;
  }
  return null;
}

// ---------------------------------------------------------------------------
// High-level fill helpers used by the per-portal fillers
// ---------------------------------------------------------------------------

/**
 * Convenience: locate a field by label and fill it. Returns true if a field
 * was found and filled (including no-op when the field already had `value`).
 */
export function fillByLabel(
  label: LabelMatcher,
  value: string | undefined,
  scope?: Element,
): boolean {
  if (value === undefined || value === "") return false;
  const el = findFieldByLabel(label, scope);
  if (!el) return false;
  if (el instanceof HTMLSelectElement) {
    setReactSelect(el, value);
  } else {
    setReactTrackedInput(el, value);
  }
  dispatchAfterFill(el);
  return true;
}

/**
 * Toggle a checkbox by its label. Idempotent: only fires when state differs.
 */
export function setCheckboxByLabel(
  label: LabelMatcher,
  checked: boolean,
  scope?: Element,
): boolean {
  const el = findFieldByLabel(label, scope);
  if (!el || !(el instanceof HTMLInputElement) || el.type !== "checkbox") {
    return false;
  }
  if (el.checked !== checked) {
    el.click();
  }
  return true;
}
