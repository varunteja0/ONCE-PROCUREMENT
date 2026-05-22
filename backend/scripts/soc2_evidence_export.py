"""CLI: bundle quarterly SOC 2 Type I evidence for a tenant.

Hits the cockpit compliance endpoints (founder-token authenticated) and
packs the responses into a single ``.zip`` along with a ``manifest.json``
that records the SHA-256 + byte length of every artifact so an auditor
can byte-match the bundle later.

Usage::

    python -m scripts.soc2_evidence_export \\
        --cockpit-url https://once.example \\
        --cockpit-token "$ONCE_COCKPIT_TOKEN" \\
        --tenant-id 037dd1ce-75e6-4364-ac39-c5ff0b43a42c \\
        --start 2026-01-01T00:00:00Z \\
        --end   2026-04-01T00:00:00Z \\
        --output evidence-2026Q1.zip

The cockpit token must belong to an operator with role ``founder`` (the
audit-export, access-review, and key-rotation POST endpoints reject
non-founders). The token can be obtained via
``POST /cockpit/auth/login``.

The script is read-only against the backend.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

_AUDIT_EXPORT_PATH = "/cockpit/compliance/audit-export"
_ACCESS_REVIEW_PATH = "/cockpit/compliance/access-review"
_HASH_DIGESTS_PATH = "/cockpit/compliance/audit-hash-digests"
_KEY_ROTATIONS_PATH = "/cockpit/compliance/key-rotations"

_DEFAULT_TIMEOUT_SEC = 60.0


@dataclass(slots=True)
class _Artifact:
    name: str
    content: bytes
    media_type: str

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()

    @property
    def bytes_len(self) -> int:
        return len(self.content)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bundle SOC 2 evidence for a single tenant + time window.",
    )
    parser.add_argument(
        "--cockpit-url",
        required=True,
        help="Base URL of the cockpit backend (e.g. https://once.example).",
    )
    parser.add_argument(
        "--cockpit-token",
        required=True,
        help="Founder operator JWT (from POST /cockpit/auth/login).",
    )
    parser.add_argument(
        "--tenant-id",
        required=True,
        help="Tenant UUID to export evidence for.",
    )
    parser.add_argument(
        "--start",
        required=True,
        help="ISO-8601 UTC start timestamp (inclusive), e.g. 2026-01-01T00:00:00Z.",
    )
    parser.add_argument(
        "--end",
        required=True,
        help="ISO-8601 UTC end timestamp (exclusive), e.g. 2026-04-01T00:00:00Z.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to the output .zip file.",
    )
    parser.add_argument(
        "--digest-page-size",
        type=int,
        default=200,
        help="Page size for audit-hash digests pagination (default 200).",
    )
    parser.add_argument(
        "--rotation-page-size",
        type=int,
        default=200,
        help="Page size for key-rotations pagination (default 200).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=_DEFAULT_TIMEOUT_SEC,
        help=f"HTTP timeout in seconds (default {_DEFAULT_TIMEOUT_SEC}).",
    )
    return parser.parse_args(argv)


def _fetch_audit_export(
    client: httpx.Client, *, tenant_id: str, start: str, end: str
) -> _Artifact:
    resp = client.get(
        _AUDIT_EXPORT_PATH,
        params={
            "tenant_id": tenant_id,
            "start": start,
            "end": end,
            "format": "jsonl",
        },
    )
    resp.raise_for_status()
    return _Artifact(
        name="audit_logs.jsonl",
        content=resp.content,
        media_type=resp.headers.get("content-type", "application/x-ndjson"),
    )


def _fetch_access_review(client: httpx.Client, *, tenant_id: str) -> _Artifact:
    resp = client.get(_ACCESS_REVIEW_PATH, params={"tenant_id": tenant_id})
    resp.raise_for_status()
    body = json.dumps(resp.json(), indent=2, sort_keys=True).encode("utf-8")
    return _Artifact(
        name="access_review.json",
        content=body,
        media_type="application/json",
    )


def _fetch_paginated(
    client: httpx.Client,
    *,
    path: str,
    params: dict[str, str | int],
    page_size: int,
    filename: str,
) -> _Artifact:
    items: list[dict[str, object]] = []
    offset = 0
    while True:
        page_params: dict[str, str | int] = {
            **params,
            "limit": page_size,
            "offset": offset,
        }
        resp = client.get(path, params=page_params)
        resp.raise_for_status()
        payload = resp.json()
        chunk = payload.get("items", [])
        items.extend(chunk)
        total = int(payload.get("total", len(items)))
        if len(items) >= total or not chunk:
            break
        offset += len(chunk)
    body = json.dumps(
        {"items": items, "total": len(items)},
        indent=2,
        sort_keys=True,
    ).encode("utf-8")
    return _Artifact(name=filename, content=body, media_type="application/json")


def _build_manifest(
    *,
    tenant_id: str,
    start: str,
    end: str,
    artifacts: list[_Artifact],
    cockpit_url: str,
) -> bytes:
    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "cockpit_url": cockpit_url,
        "tenant_id": tenant_id,
        "window": {"start": start, "end": end},
        "artifacts": [
            {
                "name": a.name,
                "media_type": a.media_type,
                "bytes": a.bytes_len,
                "sha256": a.sha256,
            }
            for a in artifacts
        ],
    }
    return json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")


def _write_zip(output_path: str, *, manifest: bytes, artifacts: list[_Artifact]) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", manifest)
        for art in artifacts:
            zf.writestr(art.name, art.content)
    with open(output_path, "wb") as fh:
        fh.write(buffer.getvalue())


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)

    headers = {
        "Authorization": f"Bearer {args.cockpit_token}",
        "Accept": "application/json",
    }
    with httpx.Client(
        base_url=args.cockpit_url.rstrip("/"),
        headers=headers,
        timeout=args.timeout,
    ) as client:
        audit = _fetch_audit_export(
            client,
            tenant_id=args.tenant_id,
            start=args.start,
            end=args.end,
        )
        access = _fetch_access_review(client, tenant_id=args.tenant_id)
        digests = _fetch_paginated(
            client,
            path=_HASH_DIGESTS_PATH,
            params={"tenant_id": args.tenant_id},
            page_size=args.digest_page_size,
            filename="audit_hash_digests.json",
        )
        rotations = _fetch_paginated(
            client,
            path=_KEY_ROTATIONS_PATH,
            params={},
            page_size=args.rotation_page_size,
            filename="key_rotations.json",
        )

    artifacts = [audit, access, digests, rotations]
    manifest = _build_manifest(
        tenant_id=args.tenant_id,
        start=args.start,
        end=args.end,
        artifacts=artifacts,
        cockpit_url=args.cockpit_url.rstrip("/"),
    )
    _write_zip(args.output, manifest=manifest, artifacts=artifacts)

    summary = {
        "output": args.output,
        "tenant_id": args.tenant_id,
        "window": {"start": args.start, "end": args.end},
        "artifacts": [
            {"name": a.name, "bytes": a.bytes_len, "sha256": a.sha256}
            for a in artifacts
        ],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
