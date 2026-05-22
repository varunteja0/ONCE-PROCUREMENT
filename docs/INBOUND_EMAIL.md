# Inbound Email (L3.9)

Once accepts inbound emails from brokers, carriers and customers and turns
them into draft submissions. Two delivery channels are supported and may run
side-by-side:

1. **Postmark inbound webhook** — recommended for production. Postmark
   handles MX, SPF/DKIM, virus scanning and retries, and POSTs JSON to our
   `/webhooks/postmark/inbound` endpoint.
2. **IMAP polling** — fallback for self-hosted dev/test where you don't
   want to point real MX records at Postmark. A Celery beat job (`inbound.poll_imap`)
   pulls new messages from any IMAP-capable mailbox and feeds them through
   the same orchestrator.

Both channels eventually call `app.services.inbound_email_service.ingest()`,
so routing, deduplication, attachment storage and spam scoring behave
identically regardless of source.

## Address scheme

Each tenant is addressable as:

```
submissions@<tenant-slug>.in.getonce.com
```

`+tag` suffixes (`submissions+amtrust@acme.in.getonce.com`) are stripped
before matching and currently ignored. Local-part-only addresses
(`<slug>@in.getonce.com`) are accepted as a fallback for tenants that
prefer a flat-namespace mailbox.

## Lifecycle

```
Postmark / IMAP
      │
      ▼
ingest()  ── idempotent on Message-ID ──► dedup short-circuit
      │
      ▼
parse To: → tenant lookup
      │
      ▼
store attachments (sha256-named, extension allowlist)
      │
      ▼
spam score 0..1 ── >= 0.9 ──► status=quarantined
      │
      ▼
select_rule() (ascending priority, first match)
      │
      ├── create_submission ──► draft Submission (status=BLOCKED)
      ├── quarantine        ──► status=quarantined
      ├── discard           ──► status=discarded
      └── tag_only          ──► status=routed, no side-effects
```

Status transitions are visible via `GET /v1/inbound` and the UI at
`/inbound`.

## Postmark setup

1. Create an inbound stream in the Postmark dashboard.
2. Point your domain's MX record at `inbound.postmarkapp.com`.
3. Set the webhook URL to:
   ```
   https://api.getonce.com/webhooks/postmark/inbound
   ```
4. Enable **HTTP Basic Auth** on the webhook. Use any username and a long
   random secret; configure the same secret in Once as
   `POSTMARK_WEBHOOK_SECRET=...`. The endpoint constant-time compares
   the entire `Authorization: Basic ...` value.
5. (Optional) If your reverse proxy enforces a small JSON body cap, raise
   it for this path to at least `30 MiB` — large multi-attachment emails
   regularly exceed the default 1 MiB used elsewhere. The endpoint
   self-enforces a 30 MiB ceiling regardless.

The endpoint always returns `200` for legitimate-but-unroutable payloads
(unknown tenant, duplicate, malformed attachment) so Postmark stops
retrying. Authentication failures return `401`; payloads larger than
30 MiB return `413`.

## IMAP setup

Set the following env vars (omit `IMAP_HOST` to disable the poller
entirely):

```
IMAP_HOST=imap.example.com
IMAP_PORT=993
IMAP_USE_SSL=true
IMAP_USERNAME=submissions@your-company.com
IMAP_PASSWORD=...
IMAP_FOLDER=INBOX
IMAP_POLL_INTERVAL_SECONDS=120
```

Run a one-shot poll for debugging:

```
python -m app.workers.imap_client --once
```

The poller persists last-seen UIDs to `<inbound_storage_path>/imap_state.json`
so it never re-ingests already-processed mail across restarts.

## Routing rules

Rules live per-tenant in `inbound_routing_rules`. They are evaluated in
**ascending priority** (lower number first) and the first match wins. A
hardcoded fallback at priority `999` ensures every email routes
somewhere — by default to a draft submission.

See [`routing_rule_examples.md`](inbound/routing_rule_examples.md) for
worked recipes.

Each rule may combine any of:

| Field                    | Meaning                                                 |
|--------------------------|---------------------------------------------------------|
| `match_from_domain`      | Right-hand-side of `From:` matches (case-insensitive). |
| `match_subject_regex`    | Python regex against `Subject:` (invalid regex = skip).|
| `match_attachment_kind`  | Lowercase extension (`pdf`, `csv`, …) present.         |
| `action`                 | `create_submission` / `quarantine` / `discard` / `tag_only`. |
| `action_params`          | Free-form JSON, passed to the router (e.g. `{"supplier_tag": "amtrust"}`). |

## Attachment safety

- Stored under `<inbound_storage_path>/<email_id>/<sha256>.<ext>` — the
  on-disk filename is *never* user-supplied.
- Extension allowlist: `pdf, csv, xlsx, xls, doc, docx, eml, txt, png, jpg, jpeg`.
  Anything else is silently dropped (logged).
- Per-attachment size cap: `INBOUND_MAX_ATTACHMENT_SIZE_MB` (default 25).
- Duplicates within a single email (same sha256) are de-duplicated.

## Spam handling

`app.services.spam_check.score_spam()` is a stub that combines:

- Keyword list ("free money", "wire transfer", …).
- ALL-CAPS subjects.
- Numeric-only local-parts.
- Presence of `X-Spam-Flag: YES` header.

Scores ≥ `0.9` automatically transition the email to `quarantined`.
The implementation is intentionally swappable — production deployments
should integrate a real classifier (SpamAssassin, rspamd, or a hosted
service).

## Troubleshooting

| Symptom                                              | Likely cause                                                 |
|------------------------------------------------------|--------------------------------------------------------------|
| Webhook returns `401`                                | `POSTMARK_WEBHOOK_SECRET` mismatch or missing `Authorization` header. |
| Webhook returns `413`                                | Email exceeded 30 MiB. Postmark itself caps at 35 MiB.       |
| Email status stuck at `received`                     | Celery worker not consuming `inbound.process` queue.         |
| Email shows `routing_failed`                         | Router raised — check `routing_error` field for details.     |
| Status `routed` but no submission                    | Matched a `tag_only` or `discard` rule.                      |
| IMAP keeps re-ingesting the same message             | `imap_state.json` missing/unwritable. Check storage path perms. |

## Production deploy checklist

- [ ] DNS MX → `inbound.postmarkapp.com`.
- [ ] Postmark inbound stream created and pointing at production webhook URL.
- [ ] `POSTMARK_WEBHOOK_SECRET` set in env (and rotated quarterly).
- [ ] `INBOUND_STORAGE_PATH` mounted on persistent volume.
- [ ] Reverse-proxy body cap raised (or sub-app routed around it) for the webhook path.
- [ ] Smoke test: send a real email to `submissions@<slug>.in.getonce.com`
      and verify it appears in `/inbound` within 30 s.
