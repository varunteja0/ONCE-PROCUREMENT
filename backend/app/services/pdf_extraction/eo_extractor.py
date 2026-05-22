"""E&O (Errors & Omissions) certificate extractor.

E&O certificates are far less standardized than ACORD 25 - every
carrier ships its own template. We rely on label/value pairs
(``Policy Number:``, ``Carrier:``, ``Effective Date:``...) with sensible
fallbacks for unlabeled fields.

Output matches a subset of :class:`~app.models.eo_certificate.EOCertificate`
column names so the upload UI can pre-fill the create form.
"""

from __future__ import annotations

from datetime import date

from app.services.pdf_extraction.base import ExtractionOutput, Page
from app.services.pdf_extraction.confidence import ConfidenceInputs, score
from app.services.pdf_extraction.patterns import (
    DATE_RE,
    POLICY_NUMBER_RE,
    find_label_value,
    find_label_value_below,
    match_insurer,
    normalize_whitespace,
    parse_date,
    parse_money_cents,
)

__all__ = ["EoExtractor"]


def _join(pages: list[Page]) -> str:
    return normalize_whitespace("\n\n".join(p.text for p in pages))


def _pick_label(text: str, labels: list[str]) -> tuple[str, float] | None:
    """Return ``(value, layout_proximity)`` if a label is found."""
    same_line = find_label_value(text, labels)
    if same_line:
        return same_line, 1.0
    below = find_label_value_below(text, labels)
    if below:
        return below, 0.8
    return None


class EoExtractor:
    document_type = "eo_certificate"
    version = "0.1.0"
    required_fields: tuple[str, ...] = (
        "carrier_name",
        "policy_number",
        "effective_date",
        "expiration_date",
    )

    def extract(self, pages: list[Page]) -> ExtractionOutput:
        out = ExtractionOutput()
        if not pages:
            out.warnings.append("no pages")
            return out

        text = _join(pages)

        # --- Carrier --------------------------------------------------------
        carrier_pair = _pick_label(
            text, ["Carrier", "Insurer", "Insurance Company", "Underwriter"]
        )
        if carrier_pair:
            raw, prox = carrier_pair
            canonical = match_insurer(raw) or raw
            out.fields["carrier_name"] = canonical
            out.confidences["carrier_name"] = score(
                ConfidenceInputs(
                    0.9 if match_insurer(raw) else 0.7,
                    prox,
                    0.7 if match_insurer(raw) else 0.5,
                )
            )
        else:
            canon = match_insurer(text)
            if canon:
                out.fields["carrier_name"] = canon
                out.confidences["carrier_name"] = score(
                    ConfidenceInputs(0.6, 0.4, 0.6)
                )

        # --- Policy number --------------------------------------------------
        pol_pair = _pick_label(
            text, ["Policy Number", "Policy #", "Policy No", "Certificate Number"]
        )
        if pol_pair:
            raw, prox = pol_pair
            # Keep only the first token-like sub-string (strip trailing notes).
            token = raw.split()[0].rstrip(",;")
            out.fields["policy_number"] = token
            out.confidences["policy_number"] = score(
                ConfidenceInputs(0.85, prox, 0.6)
            )
        else:
            for m in POLICY_NUMBER_RE.finditer(text):
                cand = m.group(1)
                if any(ch.isdigit() for ch in cand) and not cand.isdigit():
                    out.fields["policy_number"] = cand
                    out.confidences["policy_number"] = score(
                        ConfidenceInputs(0.5, 0.3, 0.4)
                    )
                    break

        # --- Named insured --------------------------------------------------
        insured_pair = _pick_label(
            text, ["Named Insured", "Insured", "Policyholder"]
        )
        if insured_pair:
            raw, prox = insured_pair
            out.fields["named_insured"] = raw
            out.confidences["named_insured"] = score(
                ConfidenceInputs(0.8, prox, 0.6)
            )

        # --- Dates ----------------------------------------------------------
        for field_name, labels in (
            ("effective_date", ["Effective Date", "Effective", "Inception Date"]),
            (
                "expiration_date",
                ["Expiration Date", "Expiration", "Expiry Date", "Expires"],
            ),
            (
                "retroactive_date",
                ["Retroactive Date", "Retro Date", "Retroactive"],
            ),
        ):
            pair = _pick_label(text, labels)
            if not pair:
                continue
            raw, prox = pair
            d = parse_date(raw)
            if d is None:
                # Sometimes the value line carries extra words; pull first date.
                mm = DATE_RE.search(raw)
                d = parse_date(mm.group(1)) if mm else None
            if d:
                out.fields[field_name] = d.isoformat()
                out.confidences[field_name] = score(
                    ConfidenceInputs(0.9, prox, 0.6)
                )

        # --- Money fields (limit + deductible) ------------------------------
        limit_pair = _pick_label(
            text,
            [
                "Limit of Liability",
                "Limit",
                "Coverage Limit",
                "Each Claim Limit",
                "Per Claim Limit",
            ],
        )
        if limit_pair:
            raw, prox = limit_pair
            cents = parse_money_cents(raw)
            if cents:
                out.fields["coverage_amount_cents"] = cents
                out.confidences["coverage_amount_cents"] = score(
                    ConfidenceInputs(0.9, prox, 0.6)
                )

        agg_pair = _pick_label(text, ["Aggregate Limit", "Aggregate"])
        if agg_pair:
            cents = parse_money_cents(agg_pair[0])
            if cents:
                out.fields["aggregate_amount_cents"] = cents
                out.confidences["aggregate_amount_cents"] = score(
                    ConfidenceInputs(0.85, agg_pair[1], 0.6)
                )

        ded_pair = _pick_label(text, ["Deductible", "Retention", "SIR"])
        if ded_pair:
            cents = parse_money_cents(ded_pair[0])
            if cents:
                out.fields["deductible_cents"] = cents
                out.confidences["deductible_cents"] = score(
                    ConfidenceInputs(0.85, ded_pair[1], 0.6)
                )

        # --- Consistency ----------------------------------------------------
        eff = out.fields.get("effective_date")
        exp = out.fields.get("expiration_date")
        if eff and exp:
            try:
                if date.fromisoformat(exp) <= date.fromisoformat(eff):
                    out.warnings.append(
                        "expiration_date is not after effective_date"
                    )
                    for k in ("effective_date", "expiration_date"):
                        out.confidences[k] = round(out.confidences[k] * 0.5, 3)
            except (TypeError, ValueError):
                pass

        return out
