"""US producer-license extractor.

State DOIs issue producer licenses in countless layouts. We pull the
high-value fields that every license carries (name, license #, state,
type, LOAs, dates, NPN) using label-value heuristics with sensible
fallbacks.
"""

from __future__ import annotations

import re
from datetime import date

from app.services.pdf_extraction.base import ExtractionOutput, Page
from app.services.pdf_extraction.confidence import ConfidenceInputs, score
from app.services.pdf_extraction.patterns import (
    DATE_RE,
    NPN_RE,
    find_label_value,
    find_label_value_below,
    guess_state_code,
    match_lines_of_authority,
    normalize_whitespace,
    parse_date,
)

__all__ = ["LicenseExtractor"]


_LICENSE_NUMBER_RE = re.compile(r"\b([A-Z0-9]{4,16})\b")


def _join(pages: list[Page]) -> str:
    return normalize_whitespace("\n\n".join(p.text for p in pages))


def _pick(text: str, labels: list[str]) -> tuple[str, float] | None:
    same = find_label_value(text, labels)
    if same:
        return same, 1.0
    below = find_label_value_below(text, labels)
    if below:
        return below, 0.8
    return None


class LicenseExtractor:
    document_type = "producer_license"
    version = "0.1.0"
    required_fields: tuple[str, ...] = (
        "licensee_name",
        "license_number",
        "state",
        "expiration_date",
    )

    def extract(self, pages: list[Page]) -> ExtractionOutput:
        out = ExtractionOutput()
        if not pages:
            out.warnings.append("no pages")
            return out

        text = _join(pages)

        # --- Licensee name --------------------------------------------------
        name_pair = _pick(
            text, ["Licensee", "Producer Name", "Name", "Agent Name", "Licensee Name"]
        )
        if name_pair:
            raw, prox = name_pair
            out.fields["licensee_name"] = raw
            out.confidences["licensee_name"] = score(
                ConfidenceInputs(0.8, prox, 0.6)
            )

        # --- License number -------------------------------------------------
        num_pair = _pick(
            text,
            [
                "License Number",
                "License #",
                "License No",
                "License ID",
                "Producer Number",
            ],
        )
        if num_pair:
            raw, prox = num_pair
            token = raw.split()[0].rstrip(",;")
            out.fields["license_number"] = token
            out.confidences["license_number"] = score(
                ConfidenceInputs(0.9, prox, 0.7)
            )
        else:
            # Heuristic: very first alphanumeric token of length 4-16 near a
            # "License" word.
            mm = re.search(
                r"(?i)license[^\n]{0,40}?([A-Z0-9]{4,16})",
                text,
            )
            if mm:
                out.fields["license_number"] = mm.group(1)
                out.confidences["license_number"] = score(
                    ConfidenceInputs(0.5, 0.4, 0.5)
                )

        # --- State ----------------------------------------------------------
        state_pair = _pick(
            text, ["State", "Issuing State", "Jurisdiction", "Domicile State"]
        )
        if state_pair:
            raw, prox = state_pair
            code = guess_state_code(raw)
            if code:
                out.fields["state"] = code
                out.confidences["state"] = score(
                    ConfidenceInputs(0.95, prox, 0.7)
                )
        if "state" not in out.fields:
            code = guess_state_code(text)
            if code:
                out.fields["state"] = code
                out.confidences["state"] = score(
                    ConfidenceInputs(0.7, 0.4, 0.5)
                )

        # --- License type ---------------------------------------------------
        type_pair = _pick(
            text, ["License Type", "Type", "Resident Status", "Residency"]
        )
        if type_pair:
            raw, prox = type_pair
            lowered = raw.lower()
            if "non" in lowered and "resident" in lowered:
                norm = "non_resident_producer"
            elif "resident" in lowered:
                norm = "resident_producer"
            elif "surplus" in lowered:
                norm = "surplus_lines"
            elif "adjust" in lowered:
                norm = "adjuster"
            elif "mga" in lowered or "managing general" in lowered:
                norm = "mga"
            elif "wholesale" in lowered:
                norm = "wholesaler"
            else:
                norm = None
            if norm:
                out.fields["license_type"] = norm
                out.confidences["license_type"] = score(
                    ConfidenceInputs(0.9, prox, 0.7)
                )

        # --- Dates ----------------------------------------------------------
        for field_name, labels in (
            (
                "effective_date",
                ["Effective Date", "Issue Date", "Issued", "Effective"],
            ),
            (
                "expiration_date",
                ["Expiration Date", "Expires", "Expiry Date", "Expiration"],
            ),
        ):
            pair = _pick(text, labels)
            if not pair:
                continue
            raw, prox = pair
            d = parse_date(raw)
            if d is None:
                mm = DATE_RE.search(raw)
                d = parse_date(mm.group(1)) if mm else None
            if d:
                out.fields[field_name] = d.isoformat()
                out.confidences[field_name] = score(
                    ConfidenceInputs(0.9, prox, 0.6)
                )

        # --- NPN ------------------------------------------------------------
        npn_pair = _pick(
            text, ["NPN", "National Producer Number", "National Producer #"]
        )
        if npn_pair:
            raw, prox = npn_pair
            mm = NPN_RE.search(raw)
            if mm:
                out.fields["npn"] = mm.group(1)
                out.confidences["npn"] = score(
                    ConfidenceInputs(0.95, prox, 0.7)
                )

        # --- Lines of authority --------------------------------------------
        loas = match_lines_of_authority(text)
        if loas:
            out.fields["lines_authorized"] = loas
            out.confidences["lines_authorized"] = score(
                ConfidenceInputs(0.85, 0.7, 0.6)
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
                        if k in out.confidences:
                            out.confidences[k] = round(out.confidences[k] * 0.5, 3)
            except (TypeError, ValueError):
                pass

        return out
