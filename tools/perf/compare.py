"""Compare the last perf run against the committed baseline.

Reads:
* ``tools/perf/baseline.csv``               — committed historical baseline
* ``tools/perf/.last_baseline_stats.csv``   — most recent ``make perf-baseline``

Diffs per-endpoint on p50 / p95 / p99 / RPS / failure %. Prints a colored
table to stdout. Exits ``1`` when any RED regression is detected (p95
worse than baseline + 20 % OR failure % worse than baseline + 0.5 pp) so
this can gate CI later.

Stdlib only (``csv`` + ``sys`` + ``pathlib``).
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_BASELINE_PATH = _HERE / "baseline.csv"
_LAST_PATH = _HERE / ".last_baseline_stats.csv"

# Thresholds — see tools/perf/README.md "What counts as a regression".
_P95_REGRESSION_PCT = 20.0
_FAILURE_REGRESSION_PP = 0.5

# Locust's stats CSV columns we care about. The header names are stable
# across locust 2.x.
_COL_TYPE = "Type"
_COL_NAME = "Name"
_COL_REQS = "Request Count"
_COL_FAILS = "Failure Count"
_COL_RPS = "Requests/s"
_COL_P50 = "50%"
_COL_P95 = "95%"
_COL_P99 = "99%"

# Aggregated row name locust emits at the bottom of stats.csv.
_AGGREGATED = "Aggregated"


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        # Still emit color when piped — most terminals strip it cleanly,
        # but skip when redirected to a file for cleanliness.
        return False
    return True


_USE_COLOR = _supports_color()
_RED = "\033[31m" if _USE_COLOR else ""
_GRN = "\033[32m" if _USE_COLOR else ""
_YEL = "\033[33m" if _USE_COLOR else ""
_DIM = "\033[2m" if _USE_COLOR else ""
_OFF = "\033[0m" if _USE_COLOR else ""


def _read_stats(path: Path) -> dict[str, dict[str, Any]]:
    """Return {endpoint_name: row_dict} for non-comment rows."""

    if not path.exists():
        return {}
    rows: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as fh:
        # Skip leading comment lines (we use `#` in baseline.csv placeholders).
        cleaned: list[str] = []
        for line in fh:
            if line.lstrip().startswith("#"):
                continue
            cleaned.append(line)
        if not cleaned:
            return {}
        reader = csv.DictReader(cleaned)
        for row in reader:
            name = (row.get(_COL_NAME) or "").strip()
            req_type = (row.get(_COL_TYPE) or "").strip()
            if not name:
                continue
            # Locust emits one "Aggregated" row with empty Type — keep it.
            key = name if req_type in ("", _AGGREGATED) else f"{req_type} {name}"
            rows[key] = row
    return rows


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _failure_pct(row: dict[str, Any]) -> float | None:
    reqs = _as_float(row.get(_COL_REQS))
    fails = _as_float(row.get(_COL_FAILS))
    if reqs is None or fails is None or reqs <= 0:
        return None
    return (fails / reqs) * 100.0


def _delta_pct(curr: float | None, base: float | None) -> str:
    if curr is None or base is None or base <= 0:
        return f"{_DIM}     —{_OFF}"
    pct = ((curr - base) / base) * 100.0
    sign = "+" if pct >= 0 else ""
    color = _GRN if pct <= 0 else (_YEL if pct <= _P95_REGRESSION_PCT else _RED)
    return f"{color}{sign}{pct:6.1f}%{_OFF}"


def _fmt_ms(value: float | None) -> str:
    if value is None:
        return f"{_DIM}    —{_OFF}"
    return f"{value:7.1f}"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return f"{_DIM}   —{_OFF}"
    return f"{value:5.2f}%"


def _verdict(
    curr_p95: float | None,
    base_p95: float | None,
    curr_fail: float | None,
    base_fail: float | None,
) -> tuple[str, bool]:
    is_red = False
    if curr_p95 is not None and base_p95 is not None and base_p95 > 0:
        if curr_p95 > base_p95 * (1.0 + _P95_REGRESSION_PCT / 100.0):
            is_red = True
    if curr_fail is not None and base_fail is not None:
        if curr_fail > base_fail + _FAILURE_REGRESSION_PP:
            is_red = True
    if is_red:
        return (f"{_RED}REGRESSION{_OFF}", True)
    if curr_p95 is None:
        return (f"{_DIM}new       {_OFF}", False)
    return (f"{_GRN}ok        {_OFF}", False)


def _print_table(
    baseline: dict[str, dict[str, Any]],
    latest: dict[str, dict[str, Any]],
) -> int:
    header = (
        f"{'Endpoint':45s}  "
        f"{'p50 (ms)':>9s} {'p95 (ms)':>9s} {'p99 (ms)':>9s}  "
        f"{'Δp95':>9s}  "
        f"{'fail%':>6s} {'Δfail':>8s}  "
        f"{'rps':>7s}  verdict"
    )
    print(header)
    print("-" * len(header))

    red_count = 0
    keys = sorted(set(baseline) | set(latest))
    for key in keys:
        b = baseline.get(key, {})
        c = latest.get(key, {})
        b_p50, b_p95, b_p99 = (
            _as_float(b.get(_COL_P50)),
            _as_float(b.get(_COL_P95)),
            _as_float(b.get(_COL_P99)),
        )
        c_p50, c_p95, c_p99 = (
            _as_float(c.get(_COL_P50)),
            _as_float(c.get(_COL_P95)),
            _as_float(c.get(_COL_P99)),
        )
        b_fail = _failure_pct(b)
        c_fail = _failure_pct(c)
        c_rps = _as_float(c.get(_COL_RPS))
        verdict, is_red = _verdict(c_p95, b_p95, c_fail, b_fail)
        if is_red:
            red_count += 1
        delta_fail = (
            f"{(c_fail - b_fail):+5.2f}pp"
            if (c_fail is not None and b_fail is not None)
            else f"{_DIM}    —{_OFF}"
        )
        print(
            f"{key[:45]:45s}  "
            f"{_fmt_ms(c_p50):>9s} {_fmt_ms(c_p95):>9s} {_fmt_ms(c_p99):>9s}  "
            f"{_delta_pct(c_p95, b_p95):>9s}  "
            f"{_fmt_pct(c_fail):>6s} {delta_fail:>8s}  "
            f"{(f'{c_rps:6.1f}' if c_rps is not None else '     —'):>7s}  "
            f"{verdict}"
        )

    print()
    if red_count:
        print(
            f"{_RED}{red_count} REGRESSION(S) detected.{_OFF} "
            "p95 worsened by > 20% or failure% by > 0.5pp."
        )
    else:
        print(f"{_GRN}No regressions vs committed baseline.{_OFF}")
    return red_count


def main() -> int:
    baseline = _read_stats(_BASELINE_PATH)
    latest = _read_stats(_LAST_PATH)

    if not latest:
        print(
            f"{_YEL}No latest run found at {_LAST_PATH}.{_OFF}\n"
            "Run `make perf-baseline` (or `make perf-smoke`) first."
        )
        return 0

    if not baseline:
        print(
            f"{_YEL}No baseline yet at {_BASELINE_PATH}.{_OFF}\n"
            "Showing latest run only. To establish a baseline:\n"
            "  make perf-baseline && cp tools/perf/.last_baseline_stats.csv "
            "tools/perf/baseline.csv\n"
        )
        _print_table({}, latest)
        return 0

    red = _print_table(baseline, latest)
    return 1 if red else 0


if __name__ == "__main__":
    raise SystemExit(main())
