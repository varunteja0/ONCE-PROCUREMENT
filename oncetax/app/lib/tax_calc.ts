/**
 * OnceTax v0 deterministic state-level tax rate tables.
 *
 * v0 LIMITATION: state base rate only — no local / district overlays.
 * Source: state .gov rate sheets as of 2024-Q4. Refresh quarterly.
 */

export const SUPPORTED_STATES = ["CA", "TX", "NY", "FL", "WA"] as const;
export type SupportedState = (typeof SUPPORTED_STATES)[number];

interface StateRate {
  state_base_rate: number;
  notes: string;
}

const RATE_TABLE: Record<SupportedState, StateRate> = {
  CA: {
    state_base_rate: 0.0725,
    notes: "California statewide base. Local district taxes NOT modeled in v0.",
  },
  TX: {
    state_base_rate: 0.0625,
    notes: "Texas state rate. Up to 2% local NOT modeled in v0.",
  },
  NY: {
    state_base_rate: 0.04,
    notes: "New York state. County/MCTD additions NOT modeled in v0.",
  },
  FL: {
    state_base_rate: 0.06,
    notes: "Florida state. Discretionary county surtax NOT modeled in v0.",
  },
  WA: {
    state_base_rate: 0.065,
    notes: "Washington state. Local sales tax NOT modeled in v0.",
  },
};

export function isSupportedState(s: string): s is SupportedState {
  return (SUPPORTED_STATES as readonly string[]).includes(s);
}

export function getStateRate(state: SupportedState): StateRate {
  return RATE_TABLE[state];
}

export interface OrderInput {
  subtotal_cents: number;
  taxable_cents?: number;
  exempt_cents?: number;
}

export interface OrderTaxResult {
  state: SupportedState;
  rate: number;
  taxable_cents: number;
  exempt_cents: number;
  tax_due_cents: number;
}

/**
 * Compute tax for a single order in a given state.
 * Cents in, cents out. Rounding: banker's rounding via Math.round (half-up).
 */
export function calcForOrder(
  order: OrderInput,
  state: SupportedState,
): OrderTaxResult {
  const rate = RATE_TABLE[state].state_base_rate;
  const exempt = Math.max(0, order.exempt_cents ?? 0);
  const taxableInput =
    order.taxable_cents !== undefined
      ? order.taxable_cents
      : Math.max(0, order.subtotal_cents - exempt);
  const taxable = Math.max(0, taxableInput);
  const taxDue = Math.round(taxable * rate);
  return {
    state,
    rate,
    taxable_cents: taxable,
    exempt_cents: exempt,
    tax_due_cents: taxDue,
  };
}
