# Billing — Stripe integration

Once uses **Stripe** for both the one-time setup fee ($2,500) and the recurring
subscription ($1,500/mo). This document covers the end-to-end lifecycle, every
webhook event we handle, local development with the Stripe CLI, and the
checklist for cutting over from test mode to live.

> All code paths default to **mock mode** (`STRIPE_MOCK_MODE=true`) so the
> backend test suite and a fresh `docker compose up` environment never hit the
> Stripe API. Flip the flag and add `STRIPE_*` keys to enable live mode.

---

## Surface map

| Layer | Path | Notes |
|---|---|---|
| Public pricing | `GET /v1/billing/pricing` | No auth. Returns plan name, prices, features. |
| Start checkout | `POST /v1/billing/checkout` | Auth required. Returns `{ checkout_url, session_id }`. |
| Open customer portal | `POST /v1/billing/portal` | Auth required. `409` if no `BillingCustomer` row. |
| Read subscription | `GET /v1/billing/subscription` | Auth required. `404` if none. |
| List invoices | `GET /v1/billing/invoices?limit&offset` | Auth required. Strictly scoped to caller's tenant. |
| Stripe webhook | `POST /webhooks/stripe` | **No `/v1/` prefix.** Public, CSRF-bypassed, HMAC-verified. |

Frontend routes:

- `/pricing` — public landing/pricing page.
- `/billing` — authed dashboard (status + invoices + Manage in Stripe).
- `/billing/success` — Stripe redirects here after Checkout.
- `/billing/cancel` — Stripe redirects here on Checkout abandonment.

---

## Data model

Five tables under `app.models.billing`:

| Table | Purpose |
|---|---|
| `billing_customers` | One row per tenant. Links to `stripe_customer_id`. |
| `billing_subscriptions` | Current + historical subscriptions; tracks status, period bounds, cancel-at-period-end. |
| `billing_invoices` | Read-mostly mirror of Stripe invoices for in-app display. |
| `billing_events` | Idempotency log of webhook events (UNIQUE on `stripe_event_id`). |
| `billing_price_configs` | Optional DB overrides for prices (falls back to env). |

Migration: `backend/app/alembic/versions/20260521_02_billing.py`.

---

## Subscription state machine

```
incomplete ──► active ──► past_due ──► (after grace) ──► unpaid
                  │            └──────► active (on successful retry)
                  ├──► trialing ──► active
                  └──► canceled  (terminal — sets tenant.is_active=false)
```

- **Non-strict mode** (default for webhook handlers): unexpected transitions
  are logged and applied anyway. Stripe is treated as the source of truth.
- **Strict mode** (operator pause/resume): rejects illegal transitions with
  `BillingStateError`.
- **Past-due grace period**: when a subscription becomes `past_due`,
  `past_due_since` is stamped. A nightly job calls
  `billing_service.apply_grace_period()` (default 7 days, configurable via
  `BILLING_GRACE_PERIOD_DAYS`) to flip to `unpaid`.
- **Canceled** is terminal. The tenant is deactivated (`is_active = False`);
  re-subscribing requires a fresh Checkout session.

---

## Webhook events handled

The webhook endpoint reads the raw body, verifies the Stripe signature
(`Stripe-Signature: t=<ts>,v1=<hex>`), claims the event in `billing_events`
(UNIQUE constraint makes claim race-safe), then dispatches:

| Event type | Effect |
|---|---|
| `checkout.session.completed` | Upserts customer + (if subscription mode) seeds an `incomplete` subscription row. |
| `customer.subscription.created` | Upserts subscription row. |
| `customer.subscription.updated` | Updates status, period bounds, cancel-at-period-end. |
| `customer.subscription.deleted` | Transitions to `canceled`; deactivates tenant. |
| `invoice.paid` | Marks invoice paid; clears `past_due_since` on the linked subscription. |
| `invoice.payment_failed` | Stamps `past_due_since`; transitions subscription to `past_due`. |
| `invoice.finalized` | Mirrors the invoice (status `open`). |
| `customer.updated` | Refreshes mirrored email/name on the local customer row. |

Unknown event types are accepted with `status: "ignored"` (Stripe retries
otherwise). Already-seen events return `status: "already_processed"`.

---

## Local development with the Stripe CLI

1. Install the [Stripe CLI](https://stripe.com/docs/stripe-cli).
2. `stripe login` (associates the CLI with your test-mode account).
3. Forward webhooks to the local backend:

   ```
   stripe listen --forward-to http://localhost:8000/webhooks/stripe
   ```

   The CLI prints a `whsec_...` secret — copy it to `STRIPE_WEBHOOK_SECRET` in
   your `.env`, then restart the backend.

4. (Optional) Trigger individual events:

   ```
   stripe trigger checkout.session.completed
   stripe trigger invoice.payment_failed
   stripe trigger customer.subscription.deleted
   ```

5. Seed your test-mode prices (one-time setup):

   ```
   cd backend
   .\.venv\Scripts\python.exe scripts/seed_stripe_prices.py
   ```

   This creates the `$2,500` one-time setup price and `$1,500/mo` recurring
   price in your Stripe test account and prints the IDs — paste them into
   `STRIPE_PRICE_SETUP_ID` and `STRIPE_PRICE_MONTHLY_ID`.

### Mock mode (default — no Stripe account needed)

With `STRIPE_MOCK_MODE=true`:

- `POST /v1/billing/checkout` returns a fake `https://checkout.stripe.com/...`
  URL and a `cs_test_*` session id.
- `POST /v1/billing/portal` returns a fake `https://billing.stripe.com/...`
  URL.
- The webhook endpoint still verifies signatures, but the helper
  `app.services.stripe_client.build_mock_signature_header()` generates valid
  HMACs against `STRIPE_WEBHOOK_SECRET`. The backend tests use this helper end
  to end.

---

## Test → Live cutover checklist

1. **Stripe Dashboard** → flip to **Live mode**.
2. Create live products + prices ($2,500 one-time, $1,500/mo) — re-run
   `scripts/seed_stripe_prices.py` against a live key, or create manually.
3. Add a live webhook endpoint pointing at `https://app.once.example.com/webhooks/stripe`.
   Subscribe to the events listed in the table above.
4. Update env (prod secrets manager — **never commit live keys**):

   ```
   STRIPE_MOCK_MODE=false
   STRIPE_SECRET_KEY=sk_live_...
   STRIPE_PUBLISHABLE_KEY=pk_live_...
   STRIPE_WEBHOOK_SECRET=whsec_<from live endpoint>
   STRIPE_PRICE_SETUP_ID=price_<live>
   STRIPE_PRICE_MONTHLY_ID=price_<live>
   STRIPE_CHECKOUT_SUCCESS_URL=https://app.once.example.com/billing/success?session_id={CHECKOUT_SESSION_ID}
   STRIPE_CHECKOUT_CANCEL_URL=https://app.once.example.com/billing/cancel
   STRIPE_CUSTOMER_PORTAL_RETURN_URL=https://app.once.example.com/billing
   ```

5. `pip install stripe` in the deploy image. The live client lazily imports
   `stripe`; mock mode does not require it.
6. Smoke test: subscribe a real tenant with a real card, confirm the webhook
   round-trips, then refund and cancel.
7. Configure Stripe's **Tax** + **Customer portal** settings in the dashboard
   (cancel reasons, update payment method, invoice history visibility).

---

## Operational notes

- Webhook endpoint **does not require CSRF** — `/webhooks/` is bypassed in
  `app.middleware.csrf`. Body-size limit (1 MiB) easily covers Stripe's ~256 KB
  max event payload.
- All Stripe writes are tenant-scoped via `BillingCustomer.tenant_id`. The
  webhook handler resolves the tenant from the linked customer row before
  applying any side-effects; events for unknown customers are logged and
  ignored (`status: "ignored"`).
- Emails stored on `BillingCustomer.email_billing` are stored as-is; logs
  redact them via `billing_service.redact_email()` (`j***@example.com`).
- The `BillingEvent` UNIQUE constraint on `stripe_event_id` is the sole source
  of webhook idempotency; concurrent retries from Stripe collapse safely.
