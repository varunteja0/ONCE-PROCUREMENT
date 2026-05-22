"""ACORD 25 Certificate-of-Insurance extractor.

The ACORD 25 (2016/03) is the canonical evidence-of-coverage form. We
extract a *superset* of what our :class:`~app.models.coi.CertificateOfInsurance`
model stores plus richer ACORD-only fields (producer block, insurer
A/B/C, additional insured flag, etc.) so the upload UI can offer a
fuller pre-filled form and let the user pick which COI rows to create.

We are deliberately permissive: missing fields are simply omitted from
the output. Confidence values are honest - if we couldn't find the
``Effective Date`` label and only had a free-floating date near the top
of the page, we'll report 0.5 not 0.95.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.services.pdf_extraction.base import ExtractionOutput, Page
from app.services.pdf_extraction.confidence import ConfidenceInputs, score
from app.services.pdf_extraction.patterns import (
    DATE_RE,
    FEIN_RE,
    POLICY_NUMBER_RE,
    find_label_value,
    find_label_value_below,
    match_insurer,
    normalize_whitespace,
    parse_date,
    parse_money_cents,
)

__all__ = ["CoiExtractor"]


_COVERAGE_TYPES: tuple[tuple[str, str], ...] = (
    ("commercial_general_liability", "commercial general liability"),
    ("automobile_liability", "automobile liability"),
    ("umbrella_liability", "umbrella liability"),
    ("excess_liability", "excess liability"),
    ("workers_compensation", "workers' compensation"),
    ("workers_compensation", "workers compensation"),
    ("employers_liability", "employers liability"),
    ("professional_liability", "professional liability"),
    ("cyber_liability", "cyber"),
)


def _join(pages: list[Page]) -> str:
    return normalize_whitespace("\n\n".join(p.text for p in pages))


def _first_block(text: str, header_patterns: list[str], max_lines: int = 6) -> str | None:
    """Return up to ``max_lines`` lines following the first matching header."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        for pat in header_patterns:
            if re.search(pat, line, re.IGNORECASE):
                collected: list[str] = []
                for j in range(i + 1, min(i + 1 + max_lines, len(lines))):
                    cand = lines[j].strip()
                    if not cand:
                        if collected:
                            break
                        continue
                    if re.match(r"(?i)^(insured|insurer|coverage|policy)", cand):
                        break
                    collected.append(cand)
                if collected:
                    return "\n".join(collected).strip()
                break
    return None


class CoiExtractor:
    document_type = "coi"
    version = "0.1.0"
    required_fields: tuple[str, ...] = (
        "carrier_name",
        "policy_number",
        "effective_date",
        "expiry_date",
    )

    def extract(self, pages: list[Page]) -> ExtractionOutput:
        out = ExtractionOutput()
        if not pages:
            out.warnings.append("no pages")
            return out

        text = _join(pages)

        # --- Producer + insured blocks --------------------------------------
        producer = _first_block(
            text,
            [
                r"^\s*PRODUCER\s*$",
                r"^\s*PRODUCER\s+",
            ],
        )
        if producer:
            out.fields["producer"] = producer
            out.confidences["producer"] = score(
                ConfidenceInputs(0.7, 0.8, 0.5)
            )

        insured = _first_block(
            text,
            [
                r"^\s*INSURED\s*$",
                r"^\s*INSURED\s+",
            ],
        )
        if insured:
            out.fields["insured"] = insured
            out.confidences["insured"] = score(
                ConfidenceInputs(0.7, 0.8, 0.5)
            )
            fein = FEIN_RE.search(insured)
            if fein:
                out.fields["insured_fein"] = fein.group(1)
                out.confidences["insured_fein"] = score(
                    ConfidenceInputs(0.95, 0.7, 0.5)
                )

        # --- Insurers A/B/C  -------------------------------------------------
        insurers: dict[str, dict[str, Any]] = {}
        insurer_pat = re.compile(
            r"(?im)^\s*INSURER\s+([A-D])\s*[:\-]?\s*(.+?)\s*(?:NAIC\s*#\s*(\d{4,6}))?\s*$"
        )
        for m in insurer_pat.finditer(text):
            slot = m.group(1).upper()
            raw_name = m.group(2).strip()
            naic = m.group(3)
            canonical = match_insurer(raw_name) or raw_name
            insurers[slot] = {
                "name": canonical,
                "raw_name": raw_name,
                "naic": naic,
            }
        if insurers:
            out.fields["insurers"] = insurers
            # Strong confidence when label found AND insurer was in lookup table.
            strong = any(
                match_insurer(i["raw_name"]) is not None for i in insurers.values()
            )
            out.confidences["insurers"] = score(
                ConfidenceInputs(
                    0.8 if strong else 0.6,
                    0.9,
                    0.7 if strong else 0.5,
                )
            )
            # Convenience: the first insurer is the primary carrier.
            first_slot = sorted(insurers.keys())[0]
            primary = insurers[first_slot]
            out.fields["carrier_name"] = primary["name"]
            out.confidences["carrier_name"] = out.confidences["insurers"]
            if primary.get("naic"):
                out.fields["carrier_naic"] = primary["naic"]
                out.confidences["carrier_naic"] = score(
                    ConfidenceInputs(0.95, 0.9, 0.7)
                )
        else:
            # Fallback: scan the doc for a known carrier substring.
            insurer = match_insurer(text)
            if insurer:
                out.fields["carrier_name"] = insurer
                out.confidences["carrier_name"] = score(
                    ConfidenceInputs(0.6, 0.4, 0.5)
                )

        # --- Policies (type + number + dates + limits) -----------------------
        policies: list[dict[str, Any]] = []
        for coverage_key, needle in _COVERAGE_TYPES:
            # Skip duplicates if already added.
            if any(p["coverage_type"] == coverage_key for p in policies):
                continue
            idx = text.lower().find(needle)
            if idx < 0:
                continue
            window = text[idx : idx + 600]
            pol = self._policy_from_window(window, coverage_key)
            if pol:
                policies.append(pol)

        if policies:
            out.fields["policies"] = policies
            out.confidences["policies"] = score(
                ConfidenceInputs(
                    0.8 if all(p.get("policy_number") for p in policies) else 0.6,
                    0.7,
                    0.6,
                )
            )
            # Promote first policy to top-level for the COI model defaults.
            primary = policies[0]
            for key in ("policy_number", "effective_date", "expiry_date"):
                if primary.get(key) and key not in out.fields:
                    out.fields[key] = primary[key]
                    out.confidences[key] = out.confidences["policies"]
            if primary.get("limit_each_occurrence") and "limit_each_occurrence" not in out.fields:
                out.fields["limit_each_occurrence_cents"] = primary[
                    "limit_each_occurrence"
                ]
                out.confidences["limit_each_occurrence_cents"] = out.confidences[
                    "policies"
                ]
            if primary.get("limit_aggregate") and "limit_aggregate" not in out.fields:
                out.fields["limit_aggregate_cents"] = primary["limit_aggregate"]
                out.confidences["limit_aggregate_cents"] = out.confidences[
                    "policies"
                ]
            out.fields["coverage_type"] = primary["coverage_type"]
            out.confidences["coverage_type"] = score(
                ConfidenceInputs(0.9, 0.8, 0.7)
            )

        # --- Certificate holder, additional insured, waiver, cert # ----------
        holder = (
            find_label_value(text, ["CERTIFICATE HOLDER", "Certificate Holder"])
            or find_label_value_below(text, ["CERTIFICATE HOLDER", "Certificate Holder"])
        )
        if holder:
            out.fields["certificate_holder"] = holder
            out.confidences["certificate_holder"] = score(
                ConfidenceInputs(0.7, 0.8, 0.5)
            )

        cert_num = (
            find_label_value(
                text, ["CERTIFICATE NUMBER", "Certificate Number", "CERT #"]
            )
            or find_label_value_below(
                text, ["CERTIFICATE NUMBER", "Certificate Number"]
            )
        )
        if cert_num:
            out.fields["certificate_number"] = cert_num.split()[0]
            out.confidences["certificate_number"] = score(
                ConfidenceInputs(0.8, 0.8, 0.6)
            )

        # Y/N indicators - look for the ACORD checkbox phrasing.
        lower = text.lower()
        out.fields["additional_insured"] = bool(
            re.search(r"additional insured\b.*\b(yes|y|x)\b", lower)
            or re.search(r"\bx\b\s*additional insured", lower)
        )
        out.confidences["additional_insured"] = score(
            ConfidenceInputs(0.6, 0.5, 0.5)
        )
        out.fields["waiver_of_subrogation"] = bool(
            re.search(r"waiver of subrogation\b.*\b(yes|y|x)\b", lower)
            or re.search(r"\bx\b\s*waiver of subrogation", lower)
        )
        out.confidences["waiver_of_subrogation"] = score(
            ConfidenceInputs(0.6, 0.5, 0.5)
        )

        # --- Cross-field consistency lift -----------------------------------
        self._apply_date_consistency(out)
        return out

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _policy_from_window(window: str, coverage_key: str) -> dict[str, Any] | None:
        out: dict[str, Any] = {"coverage_type": coverage_key}

        # Policy number candidate: prefer one prefixed by "POLICY NUMBER" or
        # "POLICY #" label; else first plausible token.
        pol = find_label_value(window, ["POLICY NUMBER", "POLICY #", "Policy #"])
        if not pol:
            mm = re.search(
                r"(?im)POLICY\s*(?:NUMBER|#)\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-\/\.]{3,31})",
                window,
            )
            if mm:
                pol = mm.group(1)
        if not pol:
            # Last-ditch: pick the first POLICY_NUMBER_RE match that has at
            # least one digit (purely alphabetic strings are usually labels).
            for m in POLICY_NUMBER_RE.finditer(window):
                cand = m.group(1)
                if any(ch.isdigit() for ch in cand) and not cand.isdigit():
                    pol = cand
                    break
        if pol:
            out["policy_number"] = pol.strip()

        # Two dates close to "EFF" / "EXP" labels.
        eff: date | None = None
        exp: date | None = None
        label_re = re.compile(
            r"(?i)(EFF(?:ECTIVE)?|EXP(?:IRATION|IRES)?)\s*(?:DATE)?\s*[:\-]?\s*"
        )
        for m in label_re.finditer(window):
            kind = m.group(1).upper()
            tail = window[m.end() : m.end() + 32]
            dm = DATE_RE.search(tail)
            if not dm:
                continue
            d = parse_date(dm.group(1))
            if d is None:
                continue
            if kind.startswith("EFF") and eff is None:
                eff = d
            elif kind.startswith("EXP") and exp is None:
                exp = d
        if eff is None or exp is None:
            # Fall back: first two date-like tokens.
            dates = [parse_date(mm.group(1)) for mm in DATE_RE.finditer(window)]
            dates = [d for d in dates if d is not None]
            if eff is None and dates:
                eff = dates[0]
            if exp is None and len(dates) > 1:
                exp = dates[1]
        if eff:
            out["effective_date"] = eff.isoformat()
        if exp:
            out["expiry_date"] = exp.isoformat()

        # Limits: pick the largest money-like figure in the window for each-
        # occurrence; second-largest for aggregate (ACORD convention).
        amounts = []
        for m in re.finditer(r"\$\s*[\d,]+(?:\.\d{1,2})?", window):
            cents = parse_money_cents(m.group(0))
            if cents and cents >= 1000_00:  # at least $1,000 — skip deductibles
                amounts.append(cents)
        amounts = sorted(set(amounts), reverse=True)
        if len(amounts) >= 2:
            # ACORD convention: aggregate >= each-occurrence. Use the two
            # largest distinct figures in that order.
            out["limit_aggregate"] = amounts[0]
            out["limit_each_occurrence"] = amounts[1]
        elif amounts:
            out["limit_each_occurrence"] = amounts[0]

        # Need at least a policy number OR (eff + exp) to count this row.
        if not out.get("policy_number") and not (
            out.get("effective_date") and out.get("expiry_date")
        ):
            return None
        return out

    @staticmethod
    def _apply_date_consistency(out: ExtractionOutput) -> None:
        eff = out.fields.get("effective_date")
        exp = out.fields.get("expiry_date")
        if not (eff and exp):
            return
        try:
            d_eff = date.fromisoformat(eff)
            d_exp = date.fromisoformat(exp)
        except (TypeError, ValueError):
            return
        if d_exp <= d_eff:
            out.warnings.append(
                f"expiry_date {exp} is not after effective_date {eff}"
            )
            for key in ("effective_date", "expiry_date"):
                if key in out.confidences:
                    out.confidences[key] = round(
                        out.confidences[key] * 0.5, 3
                    )
        else:
            # Lift both date scores by the consistency dimension.
            for key in ("effective_date", "expiry_date"):
                if key in out.confidences:
                    out.confidences[key] = min(
                        1.0, round(out.confidences[key] + 0.1, 3)
                    )
