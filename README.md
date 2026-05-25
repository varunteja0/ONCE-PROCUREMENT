# Once

> **Once — supplier-portal autopilot for specialty insurance.**

[![CI](https://img.shields.io/github/actions/workflow/status/varunteja0/ONCE-PROCUREMENT/ci.yml?branch=main&label=CI)](https://github.com/varunteja0/ONCE-PROCUREMENT/actions/workflows/ci.yml)
[![Extension](https://img.shields.io/github/actions/workflow/status/varunteja0/ONCE-PROCUREMENT/extension.yml?branch=main&label=extension)](https://github.com/varunteja0/ONCE-PROCUREMENT/actions/workflows/extension.yml)
[![Deploy backend](https://img.shields.io/github/actions/workflow/status/varunteja0/ONCE-PROCUREMENT/deploy-backend.yml?branch=main&label=deploy%20backend)](https://github.com/varunteja0/ONCE-PROCUREMENT/actions/workflows/deploy-backend.yml)
[![Deploy frontend](https://img.shields.io/github/actions/workflow/status/varunteja0/ONCE-PROCUREMENT/deploy-frontend.yml?branch=main&label=deploy%20frontend)](https://github.com/varunteja0/ONCE-PROCUREMENT/actions/workflows/deploy-frontend.yml)
[![Deploy verifier](https://img.shields.io/github/actions/workflow/status/varunteja0/ONCE-PROCUREMENT/deploy-verifier.yml?branch=main&label=deploy%20verifier)](https://github.com/varunteja0/ONCE-PROCUREMENT/actions/workflows/deploy-verifier.yml)
[![License](https://img.shields.io/badge/license-BSL%201.1-blue.svg)](LICENSE)

## Status (May 2026)

Local L2 build is **green across all four suites**, with real Playwright
submitters and the extension popup ↔ backend round-trip wired:

| Subproject   | Tests passing          |
| ------------ | ---------------------- |
| `backend/`   | **1146** (`pytest -q`, 30 integration tests skipped pending `RUN_INTEGRATION_TESTS=1`) |
| `frontend/`  | **165** (`vitest run`) |
| `extension/` | **84** (`vitest run`)  |
| `verifier/`  | **56** (`pytest -q`)   |

Real submitters in `backend/app/automation/submitters/` (with integration
tests in `backend/tests/integration/`): Vertafore AMS360, Sircon,
AmTrust, Applied Epic, Markel. Cockpit, billing, operator MFA, audit
hash-chain, verifier API keys, imports + AV, inbound email routing
(IMAP + Postmark), and the COI / LossRun / ProducerLicense /
EOCertificate / AcordForm / RiskSchedule data model are all live.

See [`LOCAL-BUILD.md`](LOCAL-BUILD.md) for the full status snapshot.

Once captures a producer/MGA submission once, fans it out to every carrier
portal that matters (AmTrust, Markel, Applied Epic, Vertafore AMS360,
Sircon …), and emits Ed25519-signed audit receipts anyone can verify.
Built for US specialty-insurance MGAs whose ops teams currently re-key
the same submission into 4–8 portals a day.

## Quickstart (5 min)

```bash
make doctor    # verify prerequisites (Python 3.12+, Node 20+, Docker, free ports)
make setup     # install everything (~3 min, idempotent)
make demo      # boot + seed + open browser (~90 sec on warm cache)
```

That's it. The dashboard opens at <http://localhost:5173>, the API at
<http://localhost:8000/docs>, and the public verifier at
<http://localhost:8080>.

Windows without GNU Make? Use the PowerShell mirror: `.\tasks.ps1 doctor`,
`.\tasks.ps1 setup`, `.\tasks.ps1 demo`. See [`CHEATSHEET.md`](CHEATSHEET.md).

**Next:**

- 👉 [`docs/QUICKSTART.md`](docs/QUICKSTART.md) — friendly walkthrough with screenshots.
- 👉 [`docs/DEMO.md`](docs/DEMO.md) — the canonical end-to-end demo script (90s tour).
- 👉 [`LOCAL-BUILD.md`](LOCAL-BUILD.md) — deeper local-build guide and current status.
- 👉 [`CONTRACTS.md`](CONTRACTS.md) — non-negotiable stack, models, env vars, file ownership.

---

## Project layout

```
once-procurement/
├── backend/       FastAPI + SQLAlchemy 2.0 async + Celery + Playwright
├── frontend/      React 18 + Vite + TanStack Query — operator console
├── extension/     MV3 (Vite + @crxjs) — fills carrier portals in-browser
├── verifier/      Public FastAPI service exposing GET /verify/{receipt_id}
├── oncetax/       Wedge B — Remix on Cloudflare Workers (D1 + R2 + KV)
├── fixtures/      Local HTML portal fixtures (AmTrust, Markel, Epic, AMS360)
├── ops/           Docker, observability, runbooks
├── tools/         perf harness, lint helpers, internal CLIs
├── gtm/           Go-to-market collateral (pitch, ICP, MSA, scripts)
├── docs/          Architecture, security, compliance, runbook, API, deploy
└── scripts/       Ops helpers: dev_doctor, dev_setup, seed_demo_tenant, …
```

## Tech stack (summary)

| Layer       | Choice                                                                  |
| ----------- | ----------------------------------------------------------------------- |
| Backend     | Python 3.12 · FastAPI · SQLAlchemy 2.0 (async) · Celery                 |
| Workers     | Playwright (Chromium) for portal automation                             |
| Database    | Postgres 16 (prod) · SQLite (unit tests, schema-portable)               |
| Frontend    | React 18 · Vite · TanStack Query · Zustand · Tailwind                   |
| Extension   | MV3 · Vite + @crxjs · WebCrypto vault                                   |
| Verifier    | Tiny stateless FastAPI service · public Ed25519 verify only             |
| OnceTax     | Remix on Cloudflare Workers · D1 + R2 + KV                              |
| Receipts    | Ed25519 signatures over canonical JSON, audit hash-chain                |
| Infra (dev) | docker compose: db · redis · backend · worker · beat · 5 nginx fixtures |

## Subproject rules

Each tree has its own `AGENTS.md` with stack-specific conventions. Read
the nearest one before editing files in that tree:

[`backend/AGENTS.md`](backend/AGENTS.md) ·
[`frontend/AGENTS.md`](frontend/AGENTS.md) ·
[`extension/AGENTS.md`](extension/AGENTS.md) ·
[`oncetax/AGENTS.md`](oncetax/AGENTS.md) ·
[`verifier/AGENTS.md`](verifier/AGENTS.md)

The root [`AGENTS.md`](AGENTS.md) is the entry point for AI coding
assistants (Copilot, Cursor, Codex, Aider, Claude Code).

## Further reading

| Doc                                                  | Why                                                    |
| ---------------------------------------------------- | ------------------------------------------------------ |
| [`CONTRACTS.md`](CONTRACTS.md)                       | Locked-in stack, model names, env vars. Normative.     |
| [`ARCHITECTURE.md`](ARCHITECTURE.md)                 | System diagram, request lifecycle, trust boundaries.   |
| [`LOCAL-BUILD.md`](LOCAL-BUILD.md)                   | Local-only build mode + current L2/L3 status.          |
| [`ROADMAP.md`](ROADMAP.md)                           | Phase plan from "demo" → "signed customers".           |
| [`BUILD.md`](BUILD.md)                               | Verify-locally commands for every subsystem.           |
| [`docs/RUNBOOK.md`](docs/RUNBOOK.md)                 | On-call procedures, key rotation, restore.             |
| [`docs/DEPLOY.md`](docs/DEPLOY.md)                   | Production deploy (Fly.io + Vercel + Cloudflare).      |
| [`docs/API.md`](docs/API.md)                         | REST catalogue with examples.                          |
| [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) | Common errors → fixes (mirrors CHEATSHEET).            |
| [`SECURITY.md`](SECURITY.md)                         | Disclosure policy — `security@once.io`, 90-day window. |
| [`CONTRIBUTING.md`](CONTRIBUTING.md)                 | Dev environment + PR conventions.                      |

## Status

Early-stage commercial product. Source is open for review, local
development, and non-production use under **Business Source License 1.1**
([`LICENSE`](LICENSE)). Production deployments require a commercial
license from Once Inc. until the BSL Change Date, after which the code
automatically converts to **Apache 2.0**.

## License

Business Source License 1.1 → Apache License 2.0 — see [`LICENSE`](LICENSE).
