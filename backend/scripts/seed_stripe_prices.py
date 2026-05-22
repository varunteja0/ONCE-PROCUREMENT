"""Seed Stripe test-mode prices for the Once Starter plan.

Usage:

    python -m scripts.seed_stripe_prices

Reads ``STRIPE_SECRET_KEY`` (must be a ``sk_test_*`` key) and creates two
prices under a single product named "Once Starter":

* ``setup``    — $2,500.00 one-time
* ``monthly``  — $1,500.00 / month recurring

After creation the script prints the IDs in env-file format. We deliberately
**do not** overwrite ``.env``; copy-paste the lines into the appropriate
environment.

In ``STRIPE_MOCK_MODE`` the script generates deterministic-looking IDs
without hitting the network so dev environments can run the seed offline.
"""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

SETUP_AMOUNT_CENTS = 250_000  # $2,500.00
MONTHLY_AMOUNT_CENTS = 150_000  # $1,500.00
PRODUCT_NAME = "Once Starter"


def _mock_price_id(kind: str) -> str:
    return f"price_test_{kind}_{secrets.token_hex(8)}"


def _create_via_stripe(api_key: str) -> tuple[str, str]:
    import stripe  # type: ignore[import-not-found]

    stripe.api_key = api_key
    product = stripe.Product.create(name=PRODUCT_NAME)
    setup = stripe.Price.create(
        product=product.id,
        currency="usd",
        unit_amount=SETUP_AMOUNT_CENTS,
        nickname="Once Starter — Setup",
    )
    monthly = stripe.Price.create(
        product=product.id,
        currency="usd",
        unit_amount=MONTHLY_AMOUNT_CENTS,
        nickname="Once Starter — Monthly",
        recurring={"interval": "month"},
    )
    return setup.id, monthly.id


def _write_env_local(setup_id: str, monthly_id: str) -> Path:
    target = Path(".env.example.local")
    lines = [
        f"STRIPE_PRICE_SETUP_ID={setup_id}\n",
        f"STRIPE_PRICE_MONTHLY_ID={monthly_id}\n",
    ]
    target.write_text("".join(lines), encoding="utf-8")
    return target


def main() -> int:
    api_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    mock_mode = os.environ.get("STRIPE_MOCK_MODE", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    if api_key and api_key.startswith("sk_live_"):
        print(
            "REFUSING to seed against a LIVE Stripe key. Re-run with sk_test_*.",
            file=sys.stderr,
        )
        return 2

    if not api_key or mock_mode:
        setup_id = _mock_price_id("setup")
        monthly_id = _mock_price_id("monthly")
        mode_note = "MOCK MODE — no Stripe API call made"
    else:
        try:
            setup_id, monthly_id = _create_via_stripe(api_key)
            mode_note = "LIVE STRIPE TEST MODE — created via API"
        except Exception as exc:  # pragma: no cover - network path
            print(f"Stripe API error: {exc}", file=sys.stderr)
            return 1

    written = _write_env_local(setup_id, monthly_id)
    print(f"# {mode_note}")
    print(f"STRIPE_PRICE_SETUP_ID={setup_id}")
    print(f"STRIPE_PRICE_MONTHLY_ID={monthly_id}")
    print(f"# Wrote {written}")
    print("# Copy the two lines above into your .env file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
