"""Phase-1 bootstrap: creates `scripts/` and `landing/` dirs and drops
all files that the sandboxed agents could not write directly.

Run ONCE from the repo root:

    python bootstrap-phase1.py

Then:

    del bootstrap-phase1.py
    del bootstrap-landing.ps1   # superseded by this script
    git add scripts/ landing/
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

FILES: dict[str, str] = {}

# -----------------------------------------------------------------
# scripts/gen_signing_key.py
# -----------------------------------------------------------------
FILES[
    "scripts/gen_signing_key.py"
] = r'''"""Generate an Ed25519 signing key for Once receipt signing.

Usage:
    python scripts/gen_signing_key.py [--key-id primary]
"""
from __future__ import annotations

import argparse
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key-id", default="primary")
    args = parser.parse_args()

    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    pub_pem = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    print("=" * 72)
    print(f"key_id: {args.key_id}")
    print("=" * 72)
    print("\n--- PRIVATE KEY PEM (set on once-backend) ---\n")
    print(priv_pem)
    print("--- PUBLIC KEY PEM (set on once-verifier) ---\n")
    print(pub_pem)
    print("=" * 72)
    print("Fly secrets:")
    print(f"  fly secrets set RECEIPT_SIGNING_KEY_ID={args.key_id} \\")
    print(f"    RECEIPT_SIGNING_PRIVATE_KEY_PEM=\"<paste priv pem>\" --app once-backend")
    print(f"  fly secrets set RECEIPT_PUBLIC_KEY_PEM=\"<paste pub pem>\" --app once-verifier")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

# -----------------------------------------------------------------
# scripts/smoke_test.py
# -----------------------------------------------------------------
FILES["scripts/smoke_test.py"] = r'''"""End-to-end smoke test for the Once stack."""
from __future__ import annotations

import argparse
import sys
import uuid

import httpx


def _log(m: str) -> None:
    print(f"[smoke] {m}", flush=True)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--api", default="http://localhost:8000")
    p.add_argument("--verifier", default="http://localhost:8080")
    args = p.parse_args()

    client = httpx.Client(base_url=args.api, timeout=15.0)
    try:
        r = client.get("/v1/health")
        assert r.status_code == 200, f"health: {r.status_code} {r.text}"
        _log(f"health ok: {r.json()}")

        email = f"smoke-{uuid.uuid4().hex[:8]}@getonce.test"
        pw = "SmokeTest!1234"
        r = client.post("/v1/auth/register", json={
            "email": email, "password": pw, "tenant_name": "Smoke MGA",
        })
        assert r.status_code in (200, 201), f"register: {r.status_code} {r.text}"
        token = r.json()["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"
        _log(f"registered {email}")

        r = client.post("/v1/auth/login", json={"email": email, "password": pw})
        assert r.status_code == 200, f"login: {r.status_code}"
        _log("login ok")

        r = client.post("/v1/suppliers", json={
            "legal_name": "Smoke Producer LLC", "ein": "12-3456789",
        })
        assert r.status_code in (200, 201), f"supplier: {r.status_code} {r.text}"
        _log(f"supplier created: {r.json().get('id')}")

        _log("CORE SMOKE OK")
        return 0
    except AssertionError as e:
        _log(f"FAIL: {e}")
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
'''

# -----------------------------------------------------------------
# scripts/smoke_test.sh
# -----------------------------------------------------------------
FILES["scripts/smoke_test.sh"] = """#!/usr/bin/env bash
set -euo pipefail
API="${1:-${API_URL:-http://localhost:8000}}"
VERIFIER="${2:-${VERIFIER_URL:-http://localhost:8080}}"
echo "[smoke] api=$API verifier=$VERIFIER"
curl -fsS "$API/v1/health" >/dev/null && echo "[smoke] api health ok"
curl -fsS "$VERIFIER/health" >/dev/null && echo "[smoke] verifier health ok"
exec python "$(dirname "$0")/smoke_test.py" --api "$API" --verifier "$VERIFIER"
"""

# -----------------------------------------------------------------
# scripts/seed_demo_tenant.py
# -----------------------------------------------------------------
FILES[
    "scripts/seed_demo_tenant.py"
] = r'''"""Seed demo tenant + portals + user. Idempotent."""
from __future__ import annotations

import asyncio
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))


async def main() -> int:
    from sqlalchemy import select
    from app.db import AsyncSessionLocal
    from app.models import Tenant, TenantUser, User, Supplier, Portal
    from app.services.auth_service import hash_password
    from app.models.portal import PortalPlatform

    demo_email = os.environ.get("DEMO_EMAIL", "demo@getonce.com")
    demo_pw = os.environ.get("DEMO_PASSWORD") or secrets.token_urlsafe(12)

    async with AsyncSessionLocal() as session:
        existing = (await session.execute(
            select(Tenant).where(Tenant.name == "Demo MGA")
        )).scalar_one_or_none()
        if existing:
            print(f"[seed] 'Demo MGA' exists: {existing.id}")
            return 0

        tenant = Tenant(name="Demo MGA")
        session.add(tenant); await session.flush()
        user = User(email=demo_email, hashed_password=hash_password(demo_pw))
        session.add(user); await session.flush()
        session.add(TenantUser(tenant_id=tenant.id, user_id=user.id, role="owner"))
        session.add(Supplier(tenant_id=tenant.id, legal_name="Acme Producer LLC", ein="12-3456789"))
        for platform in (PortalPlatform.APPLIED_EPIC, PortalPlatform.AMTRUST, PortalPlatform.MARKEL):
            existing_p = (await session.execute(
                select(Portal).where(Portal.platform == platform)
            )).scalar_one_or_none()
            if not existing_p:
                session.add(Portal(name=platform.value.replace("_", " ").title(), platform=platform))
        await session.commit()
        print("=" * 60)
        print(f"Demo seeded. login={demo_email} password={demo_pw}")
        print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
'''

# -----------------------------------------------------------------
# scripts/README.md
# -----------------------------------------------------------------
FILES["scripts/README.md"] = """# scripts/

| Script | Purpose |
|---|---|
| `gen_signing_key.py` | Generate Ed25519 receipt-signing keypair |
| `seed_demo_tenant.py` | Idempotent demo tenant + portals + user |
| `smoke_test.py` / `.sh` | End-to-end stack smoke test |

## First deploy sequence

```bash
python scripts/gen_signing_key.py --key-id primary  # capture output
# Paste `fly secrets set ...` from output (backend + verifier)
fly deploy --config fly.toml --app once-backend
fly deploy --config verifier/fly.toml --app once-verifier
fly ssh console -a once-backend -C "python /app/../scripts/seed_demo_tenant.py"
./scripts/smoke_test.sh https://api.getonce.com https://verify.getonce.com
```
"""

# -----------------------------------------------------------------
# landing/index.html
# -----------------------------------------------------------------
FILES["landing/index.html"] = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Once — Submit once. Prove it forever.</title>
  <meta name="description" content="The supplier-portal autopilot for US specialty insurance MGAs." />
  <meta property="og:title" content="Once — Submit once. Prove it forever." />
  <meta property="og:description" content="Supplier-portal autopilot for US specialty insurance MGAs." />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="https://getonce.com" />
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-white text-slate-900 antialiased font-sans">

<header class="border-b border-slate-200">
  <div class="mx-auto max-w-6xl px-6 py-5 flex items-center justify-between">
    <a href="/" class="text-xl font-bold tracking-tight"><span class="text-indigo-600">\u25cf</span> Once</a>
    <nav class="hidden sm:flex items-center gap-6 text-sm text-slate-600">
      <a href="#how" class="hover:text-slate-900">How it works</a>
      <a href="#receipts" class="hover:text-slate-900">Verifiable receipts</a>
      <a href="#demo" class="rounded-md bg-indigo-600 px-3 py-2 text-white hover:bg-indigo-500">Book a 15-min demo</a>
    </nav>
  </div>
</header>

<section class="mx-auto max-w-6xl px-6 py-20">
  <p class="text-sm uppercase tracking-wider text-indigo-600 font-semibold">Supplier-portal autopilot \u00b7 US specialty insurance MGAs</p>
  <h1 class="mt-4 text-5xl sm:text-6xl font-bold tracking-tight">Submit once.<br/>Prove it forever.</h1>
  <p class="mt-6 text-xl text-slate-600 max-w-2xl">
    MGAs waste 30\u201360% of underwriter time re-keying the same risk schedules, loss runs, ACORD forms, COIs, and producer licenses into 8\u201320 different carrier and broker portals.
  </p>
  <p class="mt-4 text-xl text-slate-600 max-w-2xl">
    <strong>Once</strong> captures the submission once and submits everywhere \u2014 with a cryptographically signed audit receipt that regulators and carriers can independently verify.
  </p>
  <div class="mt-10 flex gap-4">
    <a href="#demo" class="rounded-md bg-indigo-600 px-6 py-3 text-white font-semibold hover:bg-indigo-500">Book a 15-min demo \u2192</a>
    <a href="#how" class="rounded-md border border-slate-300 px-6 py-3 font-semibold hover:bg-slate-50">See how it works</a>
  </div>
</section>

<section class="bg-slate-50 border-y border-slate-200">
  <div class="mx-auto max-w-6xl px-6 py-20 grid sm:grid-cols-3 gap-10">
    <div><p class="text-4xl font-bold text-indigo-600">8\u201320</p><p class="mt-2 text-sm text-slate-600">Carrier + broker portals an average MGA submits to per week</p></div>
    <div><p class="text-4xl font-bold text-indigo-600">30\u201360%</p><p class="mt-2 text-sm text-slate-600">Underwriter + ops time lost re-keying the same fields</p></div>
    <div><p class="text-4xl font-bold text-indigo-600">Aug 2, 2026</p><p class="mt-2 text-sm text-slate-600">EU AI Act enforcement \u2014 auditable AI is now table stakes</p></div>
  </div>
</section>

<section id="how" class="mx-auto max-w-6xl px-6 py-20">
  <h2 class="text-3xl font-bold">How it works</h2>
  <div class="mt-10 grid sm:grid-cols-3 gap-8">
    <div class="rounded-lg border border-slate-200 p-6">
      <p class="text-sm font-semibold text-indigo-600">01 \u00b7 Capture</p>
      <h3 class="mt-2 text-lg font-bold">Once, with consent</h3>
      <p class="mt-2 text-sm text-slate-600">Producer signs a scoped consent. We capture the canonical submission packet \u2014 risk schedule, loss runs, ACORD, COIs, licenses, E&amp;O.</p>
    </div>
    <div class="rounded-lg border border-slate-200 p-6">
      <p class="text-sm font-semibold text-indigo-600">02 \u00b7 Submit</p>
      <h3 class="mt-2 text-lg font-bold">Everywhere, in parallel</h3>
      <p class="mt-2 text-sm text-slate-600">Browser automation fills AmTrust, Markel, Applied Epic, Vertafore, Sircon \u2014 every portal, in your name, with a tamper-evident audit trail.</p>
    </div>
    <div class="rounded-lg border border-slate-200 p-6">
      <p class="text-sm font-semibold text-indigo-600">03 \u00b7 Prove</p>
      <h3 class="mt-2 text-lg font-bold">Ed25519-signed receipts</h3>
      <p class="mt-2 text-sm text-slate-600">Every successful submission emits a cryptographically signed receipt. Carriers, auditors, and regulators verify independently \u2014 no Once login required.</p>
    </div>
  </div>
</section>

<section id="receipts" class="bg-slate-900 text-slate-100">
  <div class="mx-auto max-w-6xl px-6 py-20">
    <h2 class="text-3xl font-bold">Receipts you can verify</h2>
    <p class="mt-4 text-slate-300 max-w-2xl">Every submission produces a signed JSON receipt. Anyone with the URL can independently verify the signature, payload, and timestamp \u2014 without trusting Once.</p>
    <pre class="mt-8 overflow-auto rounded-lg bg-slate-800 p-6 text-xs leading-relaxed text-slate-200"><code>{
  "receipt_id": "rcp_01HXY...",
  "supplier_id": "sup_01HXY...",
  "portal": "amtrust",
  "submitted_at": "2026-05-19T10:14:22Z",
  "signer_key_id": "primary",
  "algorithm": "ed25519",
  "signature": "qX9...base64..."
}</code></pre>
    <p class="mt-6 text-sm text-slate-400">Verify at <code class="text-indigo-300">verify.getonce.com/verify/&lt;receipt_id&gt;</code></p>
  </div>
</section>

<section id="demo" class="mx-auto max-w-6xl px-6 py-20 text-center">
  <h2 class="text-3xl font-bold">Want to see it on your portals?</h2>
  <p class="mt-4 text-slate-600 max-w-xl mx-auto">15-minute call. We will demo on a real MGA workflow and quote a 30-day pilot.</p>
  <a href="https://cal.com/once/demo" class="mt-8 inline-block rounded-md bg-indigo-600 px-8 py-4 text-white font-semibold hover:bg-indigo-500">Book a 15-min demo \u2192</a>
</section>

<footer class="border-t border-slate-200">
  <div class="mx-auto max-w-6xl px-6 py-10 flex flex-col sm:flex-row items-center justify-between text-sm text-slate-500">
    <p>\u00a9 2026 Once, Inc. Delaware C-corp.</p>
    <nav class="mt-4 sm:mt-0 flex gap-6">
      <a href="/privacy" class="hover:text-slate-900">Privacy</a>
      <a href="/terms" class="hover:text-slate-900">Terms</a>
      <a href="/security" class="hover:text-slate-900">Security</a>
      <a href="mailto:hello@getonce.com" class="hover:text-slate-900">hello@getonce.com</a>
    </nav>
  </div>
</footer>

</body>
</html>
"""

# -----------------------------------------------------------------
# landing/vercel.json
# -----------------------------------------------------------------
FILES["landing/vercel.json"] = """{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "cleanUrls": true,
  "trailingSlash": false,
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "Strict-Transport-Security", "value": "max-age=63072000; includeSubDomains; preload" },
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
        { "key": "Permissions-Policy", "value": "camera=(), microphone=(), geolocation=()" },
        { "key": "Content-Security-Policy", "value": "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cal.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; frame-src https://cal.com https://app.cal.com; connect-src 'self' https://cal.com; base-uri 'self'; form-action 'self'" }
      ]
    }
  ]
}
"""

# -----------------------------------------------------------------
# landing/README.md
# -----------------------------------------------------------------
FILES["landing/README.md"] = """# landing \u2014 getonce.com marketing site

Single static page deployed as a separate Vercel project from `frontend/`.

## Local preview

```bash
cd landing
python -m http.server 8000
```

## Deploy (Vercel project `once-landing`)

```bash
vercel link
vercel --prod
```
"""


def main() -> int:
    written = 0
    for relpath, content in FILES.items():
        full = ROOT / relpath
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        print(f"  wrote {relpath}  ({len(content)} chars)")
        written += 1
    # make smoke_test.sh executable on Unix
    sh = ROOT / "scripts" / "smoke_test.sh"
    try:
        os.chmod(sh, 0o755)
    except OSError:
        pass
    print(f"\nDone. {written} files written.")
    print(
        "Next: del bootstrap-phase1.py bootstrap-landing.ps1 && git add scripts/ landing/"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
