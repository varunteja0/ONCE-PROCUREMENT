"""Per-field confidence scoring.

Confidence in ``[0.0, 1.0]`` combines three sources of evidence:

1. ``regex_strength``   - how unambiguous the regex match was. A purely
   numeric NPN is 1.0; a 4-char fragment we *think* is a policy
   number is 0.5.
2. ``layout_proximity`` - distance between the label we matched on
   (e.g. ``Effective Date``) and the value we kept. Same line = 1.0,
   next non-empty line = 0.8, further = 0.5, no label at all = 0.4.
3. ``consistency``      - does the field agree with sibling fields?
   ``expiration_date > effective_date`` lifts both; insurer name
   matching the carrier lookup table lifts the carrier field.

Final = ``0.5 * regex_strength + 0.3 * layout_proximity + 0.2 * consistency``
clamped to ``[0.0, 1.0]`` and rounded to 3 d.p. for stable JSON output.

The UI maps the score to color:

* ``>= 0.9`` green  - accept without review.
* ``0.6 - 0.9`` yellow - review recommended.
* ``< 0.6`` red - likely wrong, please correct.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "ConfidenceInputs",
    "score",
    "GREEN_THRESHOLD",
    "YELLOW_THRESHOLD",
    "label",
]


GREEN_THRESHOLD: float = 0.9
YELLOW_THRESHOLD: float = 0.6


@dataclass(frozen=True, slots=True)
class ConfidenceInputs:
    regex_strength: float = 0.5
    layout_proximity: float = 0.5
    consistency: float = 0.5


def _clamp(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def score(inputs: ConfidenceInputs) -> float:
    raw = (
        0.5 * _clamp(inputs.regex_strength)
        + 0.3 * _clamp(inputs.layout_proximity)
        + 0.2 * _clamp(inputs.consistency)
    )
    return round(_clamp(raw), 3)


def label(value: float) -> str:
    if value >= GREEN_THRESHOLD:
        return "green"
    if value >= YELLOW_THRESHOLD:
        return "yellow"
    return "red"
