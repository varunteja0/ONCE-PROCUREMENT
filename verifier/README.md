# Once Receipt Verifier

> Standalone, Apache-2.0-licensed microservice that verifies Once submission
> receipts using only published public keys. Run it yourself. Run it in a
> regulator's network. Audit Once without trusting Once.

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](./LICENSE)

## Why this exists

Once seals every carrier submission with an Ed25519 signature over a
deterministic, [RFC 8785](https://datatracker.ietf.org/doc/html/rfc8785)
canonical JSON payload. That signature is worthless if the only way to verify
it is to ask Once. This service exists so that:

- **Customers** can independently confirm what was submitted, when, and to which
  portal, without trusting the Once backend.
- **E&O insurers** can validate receipt evidence as part of premium discount
  programs (see `docs/PARTNER_EO.md`).
- **Regulators** can host a verifier on their own infrastructure and re-check
  any past or future submission.

This subtree is licensed under **Apache 2.0** (see [`LICENSE`](./LICENSE) and
[`NOTICE`](./NOTICE)). The rest of the repository is BSL 1.1 with a 2029-01-27
change date — we ship the verifier permissively today so trust is never gated
on a license question.

## Routes

| Route                                | Purpose                                                                 |
| ------------------------------------ | ----------------------------------------------------------------------- |
| `GET /healthz`, `GET /health`        | Liveness probe — returns `{"status":"ok"}`.                             |
| `GET /verify/{receipt_id}`           | Verify and render an HTML report. Auto-content-negotiates with `.html`. |
| `GET /verify/{receipt_id}.json`      | Machine-readable verification result.                                   |
| `GET /verify/{receipt_id}.html`      | Human-readable HTML page (the same that `/verify/{id}` renders).        |
| `GET /verify/{receipt_id}/badge.svg` | SVG badge ("Once: VALID" / "Once: INVALID") for embedding.              |
| `GET /verify/{receipt_id}/og.svg`    | Social-card-sized SVG for previews.                                     |

All routes are public, stateless, idempotent, and require no auth.

## Install

```bash
cd verifier
python -m venv .venv
. .venv/bin/activate    # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```bash
export PUBLIC_KEY_PEM="$(curl -s https://getonce.com/v1/public/keys.txt)"
export BACKEND_BASE_URL="https://getonce.com"
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

### Environment variables

| Variable           | Required | Description                                                                                                                                                                                                   |
| ------------------ | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `BACKEND_BASE_URL` | yes      | Base URL of the Once API (e.g. `https://getonce.com`).                                                                                                                                                        |
| `PUBLIC_KEY_PEM`   | no       | Pinned public key(s) in PEM format. If unset, the service trusts the keys returned by `BACKEND_BASE_URL/v1/public/keys`. For maximum independence, pin keys you obtained out-of-band (DNS TXT, NOTICE, etc.). |
| `LOG_LEVEL`        | no       | Defaults to `INFO`.                                                                                                                                                                                           |

See [`docs/PUBLIC_TRUST_KEYS.md`](../docs/PUBLIC_TRUST_KEYS.md) for the
DNS-publication procedure used to pin keys.

## Test

```bash
pip install -r requirements.txt
pytest -q
```

## Deploy

A `Dockerfile` and `fly.toml` are provided. The service is single-process,
stateless, and intended to be horizontally scaled behind a load balancer.

## Reporting issues

For security-sensitive issues, please follow `SECURITY.md` at the repo root.
General issues: GitHub Issues on the main `once-procurement` repository.

## Related documents

- Root [`CONTRACTS.md`](../CONTRACTS.md) — canonical receipt schema and signing rules.
- [`docs/VERIFIER.md`](../docs/VERIFIER.md) — operator-focused runbook.
- [`docs/MOAT.md`](../docs/MOAT.md) — why "verify without trusting us" is a moat.
- [`docs/PUBLIC_TRUST_KEYS.md`](../docs/PUBLIC_TRUST_KEYS.md) — DNS-TXT key publication.
