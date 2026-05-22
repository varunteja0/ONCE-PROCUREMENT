# Routing rule cookbook

All examples assume tenant slug `acme` and inbound address
`submissions@acme.in.getonce.com`. Use the REST endpoints under
`/v1/inbound/rules` or the UI at `/inbound/rules`.

Lower `priority` wins. Leave space (10/20/30/…) so manual edits stay
ergonomic.

## 1. AmTrust forwarded quotes → tagged submission

```json
{
  "name": "AmTrust forwards",
  "priority": 10,
  "match_from_domain": "amtrustfinancial.com",
  "action": "create_submission",
  "action_params": { "supplier_tag": "amtrust", "channel": "email_forward" }
}
```

## 2. Broker submissions (PDF attached)

```json
{
  "name": "Broker submissions with PDF",
  "priority": 20,
  "match_subject_regex": "(?i)(submission|quote request)",
  "match_attachment_kind": "pdf",
  "action": "create_submission"
}
```

## 3. COI updates → submission with COI tag

```json
{
  "name": "Certificate of insurance updates",
  "priority": 30,
  "match_subject_regex": "(?i)\\b(coi|certificate of insurance)\\b",
  "action": "create_submission",
  "action_params": { "document_kind": "coi" }
}
```

## 4. Loss-run forwards (CSV/XLSX)

```json
{
  "name": "Loss runs",
  "priority": 40,
  "match_subject_regex": "(?i)loss run",
  "match_attachment_kind": "xlsx",
  "action": "create_submission",
  "action_params": { "document_kind": "loss_run" }
}
```

## 5. ACORD form intakes

```json
{
  "name": "ACORD forms",
  "priority": 50,
  "match_subject_regex": "(?i)acord ?(125|126|140)",
  "action": "create_submission",
  "action_params": { "document_kind": "acord" }
}
```

## 6. Marketing spam from known offenders

```json
{
  "name": "Quarantine marketing blasts",
  "priority": 5,
  "match_from_domain": "marketing.example",
  "action": "quarantine"
}
```

Priority `5` puts this rule *before* the more specific routes — useful
when you've seen a particular domain consistently flood your inbox.

## Notes

- Invalid regex in `match_subject_regex` causes the rule to be skipped
  (never raises), so a typo can't break ingestion for the whole tenant.
- The fallback rule at priority `999` always runs `create_submission`,
  so emails that match no rule still produce a draft.
- `tag_only` is useful for analytics-only flows where you want the
  message stored but no submission created.
