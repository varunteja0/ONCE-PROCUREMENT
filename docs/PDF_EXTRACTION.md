# PDF metadata extraction (L3.8)

Once ships a tenant-scoped extractor pipeline that pulls structured
fields out of three classes of insurance PDFs:

| Source document  | Source-type code     | Extractor                                                | Required fields |
|------------------|----------------------|----------------------------------------------------------|-----------------|
| ACORD 25 COI     | `coi`                | `app.services.pdf_extraction.coi_extractor.CoiExtractor` | `policy_number`, `effective_date`, `expiry_date` |
| E&O certificate  | `eo_certificate`     | `EoExtractor`                                            | `carrier_name`, `policy_number`, `effective_date`, `expiration_date` |
| Producer license | `producer_license`   | `LicenseExtractor`                                       | `licensee_name`, `license_number`, `state` |

Every extraction produces a row in `extraction_results` with:

* `extracted_fields` — a JSON map of canonical field names → values
  (dates ISO-8601, money in cents, booleans for Y/N flags).
* `field_confidences` — JSON map of field → score in `[0, 1]`.
* `warnings` — JSON list of soft-failure reasons (e.g. `"effective_date
  and expiry_date are inverted"`).
* `status` — state machine: `pending → succeeded | partial | failed` →
  `accepted | rejected` (operator review).

## Confidence model

`field_confidence = 0.5 · regex_strength + 0.3 · layout_match + 0.2 · consistency`

| Tier   | Threshold     | UI       |
|--------|---------------|----------|
| Green  | `≥ 0.90`      | accept-by-default |
| Yellow | `0.60–0.89`   | needs review      |
| Red    | `< 0.60`      | almost certainly needs an override |

Constants live in `app/services/pdf_extraction/confidence.py`.

## HTTP API

All routes are tenant-scoped via the standard `Authorization: Bearer
<jwt>` header.

| Method | Path                                  | Purpose                                              |
|--------|---------------------------------------|------------------------------------------------------|
| POST   | `/v1/extractions/document`            | Enqueue an extraction for a `(document_type, document_id)` |
| GET    | `/v1/extractions/{id}`                | Fetch a single extraction (status, fields, confidences) |
| GET    | `/v1/extractions`                     | Paginated list (`document_type`, `limit`, `offset`)   |
| POST   | `/v1/extractions/{id}/accept`         | Accept (optional field overrides merged in)          |
| POST   | `/v1/extractions/{id}/reject`         | Reject (optional reason recorded in `warnings`)      |

All write endpoints emit an `audit_logs` row (`extraction.enqueued`,
`extraction.accepted`, `extraction.rejected`).

## Worker

`POST /v1/extractions/document` enqueues a Celery task
`extractions.extract_document` (in
`app/workers/tasks/extraction_tasks.py`). The task runs the
orchestrator in
`app/services/extraction_service.run_extraction`, which:

1. Loads the PDF via the configured `PdfLoader` (default
   `InMemoryPdfLoader`; production swaps in an S3 / disk loader).
2. Validates magic bytes + size + encryption hint
   (`text_extractor.validate_pdf_header`).
3. Runs PyMuPDF (preferred) → falls back to pdfminer.six
   (`text_extractor.extract_pages`).
4. Dispatches to the registered extractor for the source type and
   persists fields/confidences/warnings.
5. Classifies the row as `succeeded` / `partial` / `failed` based on
   `BasePdfExtractor.required_fields` and confidence thresholds.

Failures never raise — every error path records `status="failed"` and
populates `error` (`"pdf_encrypted"`, `"pdf_too_large: …"`,
`"loader: …"`, `"extractor_timeout"`, `"extractor: …"`).

## Frontend

```
frontend/src/services/extractionsApi.ts        # typed wrappers
frontend/src/hooks/useExtraction.ts            # react-query hooks
frontend/src/components/extraction/
  ConfidenceBadge.tsx                          # colored pill
  ExtractedFieldsPanel.tsx                     # editable form
  ExtractionAwareUpload.tsx                    # drop-in wrapper for existing pages
```

`ExtractionAwareUpload` polls `GET /v1/extractions/{id}` every 2s
while `status="pending"`, then renders `ExtractedFieldsPanel` with a
text input next to every primitive field, plus accept / reject
buttons. Existing upload pages keep their layout — wrap them in
`<ExtractionAwareUpload documentType="coi" documentId={coi.id}>...</>`
to opt in.

## Adding a new extractor

1. Implement `BasePdfExtractor` in
   `app/services/pdf_extraction/<name>_extractor.py`:

   ```python
   from app.services.pdf_extraction.base import BasePdfExtractor, ExtractionOutput, Page

   class MyExtractor:
       source_type = "my_doc"
       version = "my-1.0.0"
       required_fields = ("field_a", "field_b")

       def extract(self, pages: list[Page]) -> ExtractionOutput:
           ...
   ```

2. Register it in `app/services/pdf_extraction/__init__.py`'s
   `EXTRACTORS` dict.

3. Add the new value to `ExtractionSourceType` in
   `app/models/extraction_result.py`.

4. Drop a test in `backend/tests/test_<name>_extractor.py` using the
   `tests/fixtures/pdfs.make_pdf` helper.

## Limitations (Phase 3)

* **Text-layer only.** Scanned / image-only PDFs return no text and
  fail extraction with no fields. No OCR pass yet.
* **English-only regexes**, US-centric state codes and date formats.
* **Encryption detection is heuristic** (`/Encrypt` substring in the
  first 64 KB). Real password-protected PDFs are correctly rejected;
  some edge cases may slip through and fail downstream parsing — also
  classified as `failed`.
* **No table reconstruction.** ACORD 25 limits/dates are pulled
  per-coverage-block, not from the gridded table.
* **PDF size hard cap**: 25 MB, 50 pages (configurable via
  `settings.pdf_max_size_mb` and `settings.pdf_max_pages`).

## Phase 4 roadmap

* **Vision LLM fallback** for any field with confidence `< 0.6` or for
  pages with no extracted text (scanned ACORD 25s).
* **Hand-labeled gold set** of 200 real-world PDFs to measure recall /
  precision per field per extractor and gate releases.
* **Layout-aware extractors** (PyMuPDF text blocks → table
  reconstruction) for the ACORD 25 grid.
* **Multi-language support** (ES, FR-CA) once we have customer demand.
* **Replay / re-extract** endpoint to re-run an extraction after
  patterns or models change without uploading the PDF again.
