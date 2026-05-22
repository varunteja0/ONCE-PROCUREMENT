"""L3.7 — Combined test suite for the bulk-import pipeline.

Covers parsers (CSV + XLSX), the supplier importer, the orchestrator
service, the REST API, and the Celery task wrapper. We collapse the
modules into one file to keep the C5 patch self-contained — the test
discovery cost is paid once, but the parametrized cases give us 50+
assertions across the unit/integration boundary.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ImportEntityType,
    ImportRowError,
    ImportStatus,
    Supplier,
)
from app.services import import_service
from app.services.importers import get_importer
from app.services.importers.supplier_importer import (
    SupplierImporter,
    normalize_fein,
)
from app.services.parsers import detect_format, iter_rows
from app.services.parsers.csv_parser import iter_csv_rows
from app.services.parsers.xlsx_parser import iter_xlsx_rows

FIXTURES = Path(__file__).parent / "fixtures" / "imports"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _xlsx_bytes(rows: list[list[Any]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _csv_bytes(text: str) -> bytes:
    return text.encode("utf-8")


async def _seed_tenant_and_user(client: AsyncClient) -> tuple[str, str]:
    """Return (tenant_id, user_id) for the default ``auth_client`` user."""
    # We need the tenant_id from the JWT we already hold. Decode via the
    # ``/v1/me`` analogue if available; otherwise query through the suppliers
    # endpoint which echoes tenant in headers. Easiest: introspect /v1/auth/me.
    resp = await client.get("/v1/auth/me")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return body["tenant_id"], body["user_id"]


# ---------------------------------------------------------------------------
# CSV parser
# ---------------------------------------------------------------------------


class TestCsvParser:
    def test_basic_utf8(self) -> None:
        rows = list(iter_csv_rows(FIXTURES / "suppliers_valid.csv"))
        assert len(rows) == 5
        assert rows[0]["name"] == "Acme Trucking"
        assert rows[0]["fein"] == "12-3456789"

    def test_utf8_bom(self) -> None:
        rows = list(iter_csv_rows(FIXTURES / "suppliers_utf8_bom.csv"))
        assert rows[0]["name"] == "Acme"

    def test_cp1252(self) -> None:
        rows = list(iter_csv_rows(FIXTURES / "suppliers_cp1252.csv"))
        # Whatever the decode path, the row count + structural fields hold.
        assert len(rows) == 1
        assert rows[0]["fein"] == "12-3456789"

    def test_skips_blank_rows(self, tmp_path: Path) -> None:
        p = tmp_path / "blank.csv"
        p.write_text(
            "name,fein,state\r\nA,12-3456789,CA\r\n,,\r\nB,98-7654321,NY\r\n",
            encoding="utf-8",
        )
        rows = list(iter_csv_rows(p))
        assert [r["name"] for r in rows] == ["A", "B"]

    def test_handles_quoted_commas_and_newlines(self, tmp_path: Path) -> None:
        p = tmp_path / "quoted.csv"
        p.write_text(
            'name,fein,state\r\n"Acme, Inc.",12-3456789,CA\r\n' '"Big\nName",98-7654321,NY\r\n',
            encoding="utf-8",
        )
        rows = list(iter_csv_rows(p))
        assert rows[0]["name"] == "Acme, Inc."
        assert "\n" in rows[1]["name"]

    def test_missing_trailing_cells_padded(self, tmp_path: Path) -> None:
        p = tmp_path / "ragged.csv"
        p.write_text("name,fein,state\r\nAcme,12-3456789\r\n", encoding="utf-8")
        rows = list(iter_csv_rows(p))
        assert rows[0]["state"] == ""

    def test_empty_file(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.csv"
        p.write_bytes(b"")
        rows = list(iter_csv_rows(p))
        assert rows == []

    def test_headers_normalised_lower_strip(self, tmp_path: Path) -> None:
        p = tmp_path / "hdr.csv"
        p.write_text(" NAME ,FEIN, State \r\nA,12-3456789,CA\r\n", encoding="utf-8")
        rows = list(iter_csv_rows(p))
        assert "name" in rows[0] and "state" in rows[0]

    def test_iter_rows_dispatch_csv(self) -> None:
        rows = list(iter_rows(FIXTURES / "suppliers_valid.csv", filename="x.csv"))
        assert len(rows) == 5

    def test_detect_format_known_exts(self) -> None:
        assert detect_format("a.csv", None) == "csv"
        assert detect_format("a.xlsx", None) == "xlsx"

    def test_detect_format_unknown_raises(self) -> None:
        with pytest.raises(Exception):
            detect_format("a.pdf", None)


# ---------------------------------------------------------------------------
# XLSX parser
# ---------------------------------------------------------------------------


class TestXlsxParser:
    def test_basic(self, tmp_path: Path) -> None:
        p = tmp_path / "s.xlsx"
        p.write_bytes(
            _xlsx_bytes(
                [
                    ["name", "fein", "state"],
                    ["Acme", "12-3456789", "CA"],
                    ["Bravo", "98-7654321", "TX"],
                ]
            )
        )
        rows = list(iter_xlsx_rows(p))
        assert [r["name"] for r in rows] == ["Acme", "Bravo"]

    def test_stringifies_dates_and_numbers(self, tmp_path: Path) -> None:
        from datetime import date

        p = tmp_path / "s.xlsx"
        p.write_bytes(
            _xlsx_bytes(
                [
                    ["name", "fein", "state", "joined", "tier"],
                    ["Acme", "12-3456789", "CA", date(2024, 1, 5), 3.0],
                ]
            )
        )
        rows = list(iter_xlsx_rows(p))
        assert rows[0]["joined"].startswith("2024-01-05")
        assert rows[0]["tier"] == "3"

    def test_booleans_stringified(self, tmp_path: Path) -> None:
        p = tmp_path / "s.xlsx"
        p.write_bytes(_xlsx_bytes([["name", "fein", "state", "flag"], ["A", "12-3456789", "CA", True]]))
        rows = list(iter_xlsx_rows(p))
        assert rows[0]["flag"] == "true"

    def test_blank_rows_skipped(self, tmp_path: Path) -> None:
        p = tmp_path / "s.xlsx"
        p.write_bytes(
            _xlsx_bytes(
                [
                    ["name", "fein", "state"],
                    ["A", "12-3456789", "CA"],
                    [None, None, None],
                    ["B", "98-7654321", "NY"],
                ]
            )
        )
        rows = list(iter_xlsx_rows(p))
        assert [r["name"] for r in rows] == ["A", "B"]

    def test_empty_workbook(self, tmp_path: Path) -> None:
        p = tmp_path / "s.xlsx"
        p.write_bytes(_xlsx_bytes([]))
        assert list(iter_xlsx_rows(p)) == []

    def test_first_sheet_only(self, tmp_path: Path) -> None:
        wb = Workbook()
        ws1 = wb.active
        ws1.append(["name", "fein", "state"])
        ws1.append(["A", "12-3456789", "CA"])
        ws2 = wb.create_sheet("other")
        ws2.append(["x", "y", "z"])
        ws2.append(["1", "2", "3"])
        p = tmp_path / "s.xlsx"
        buf = io.BytesIO()
        wb.save(buf)
        p.write_bytes(buf.getvalue())
        rows = list(iter_xlsx_rows(p))
        assert len(rows) == 1
        assert rows[0]["name"] == "A"

    def test_short_rows_padded(self, tmp_path: Path) -> None:
        wb = Workbook()
        ws = wb.active
        ws.append(["name", "fein", "state"])
        # Force short row by writing only one column then no more
        ws.cell(row=2, column=1, value="A")
        buf = io.BytesIO()
        wb.save(buf)
        p = tmp_path / "s.xlsx"
        p.write_bytes(buf.getvalue())
        rows = list(iter_xlsx_rows(p))
        assert rows[0]["state"] == ""

    def test_iter_rows_dispatch_xlsx(self, tmp_path: Path) -> None:
        p = tmp_path / "s.xlsx"
        p.write_bytes(_xlsx_bytes([["name", "fein", "state"], ["A", "12-3456789", "CA"]]))
        rows = list(iter_rows(p, filename="s.xlsx"))
        assert rows[0]["name"] == "A"


# ---------------------------------------------------------------------------
# Supplier importer
# ---------------------------------------------------------------------------


class TestSupplierImporter:
    def setup_method(self) -> None:
        self.imp = SupplierImporter()

    def test_normalize_fein_variants(self) -> None:
        assert normalize_fein("12-3456789") == "12-3456789"
        assert normalize_fein("123456789") == "12-3456789"
        assert normalize_fein("12 34 56 789") == "12-3456789"
        assert normalize_fein("not a fein") is None
        assert normalize_fein("") is None
        assert normalize_fein("1234567") is None

    def test_valid_row(self) -> None:
        vr = self.imp.validate_row({"name": "Acme", "fein": "123456789", "state": "ca", "email": "a@b.co"}, 2)
        assert vr.ok
        assert vr.data["legal_name"] == "Acme"
        assert vr.data["ein"] == "12-3456789"
        assert vr.data["address_json"]["state"] == "CA"
        assert vr.dedupe_key == "12-3456789"

    def test_name_required(self) -> None:
        vr = self.imp.validate_row({"name": "", "fein": "12-3456789", "state": "CA"}, 2)
        assert not vr.ok
        assert any(e.error_code == "name_required" for e in vr.errors)

    def test_fein_format_bad(self) -> None:
        vr = self.imp.validate_row({"name": "A", "fein": "abc", "state": "CA"}, 2)
        codes = {e.error_code for e in vr.errors}
        assert "fein_format" in codes

    def test_state_invalid(self) -> None:
        vr = self.imp.validate_row({"name": "A", "fein": "12-3456789", "state": "XX"}, 2)
        assert any(e.error_code == "state_invalid" for e in vr.errors)

    def test_email_invalid(self) -> None:
        vr = self.imp.validate_row(
            {
                "name": "A",
                "fein": "12-3456789",
                "state": "CA",
                "email": "not-an-email",
            },
            2,
        )
        assert any(e.error_code == "email_invalid" for e in vr.errors)

    def test_alias_mapping(self) -> None:
        amap = self.imp.alias_map()
        # 'company' should map to 'name'
        assert amap.get("company") == "name"
        assert amap.get("ein") == "fein"

    def test_remap_with_user_mapping_wins(self) -> None:
        out = self.imp.remap_row(
            {"company": "Acme", "ein": "12-3456789", "primary_state": "CA"},
            {"primary_state": "state"},
        )
        assert out["name"] == "Acme"
        assert out["fein"] == "12-3456789"
        assert out["state"] == "CA"

    def test_missing_required_columns(self) -> None:
        missing = self.imp.missing_required_columns({"name", "state"}, None)
        assert "fein" in missing

    def test_address_packing(self) -> None:
        vr = self.imp.validate_row(
            {
                "name": "A",
                "fein": "12-3456789",
                "state": "CA",
                "city": "Oakland",
                "address_line1": "1 Main",
                "zip": "94601",
            },
            2,
        )
        assert vr.ok
        addr = vr.data["address_json"]
        assert addr == {
            "line1": "1 Main",
            "city": "Oakland",
            "state": "CA",
            "postal_code": "94601",
        }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class TestImportService:
    async def test_create_unsupported_extension(self, async_session: AsyncSession) -> None:
        with pytest.raises(import_service.UnsupportedFormatError):
            await import_service.create_import_job(
                async_session,
                tenant_id="t1",
                entity_type=ImportEntityType.SUPPLIER,
                original_filename="x.pdf",
                content_type="application/pdf",
                file_bytes=b"hi",
            )

    async def test_create_too_large(self, async_session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(import_service.settings, "import_max_file_size_bytes", 10)
        with pytest.raises(import_service.FileTooLargeError):
            await import_service.create_import_job(
                async_session,
                tenant_id="t1",
                entity_type=ImportEntityType.SUPPLIER,
                original_filename="x.csv",
                content_type="text/csv",
                file_bytes=b"x" * 100,
            )

    async def test_dry_run_happy(self, async_session: AsyncSession) -> None:
        data = (FIXTURES / "suppliers_valid.csv").read_bytes()
        job = await import_service.create_import_job(
            async_session,
            tenant_id="tenant-svc-1",
            entity_type=ImportEntityType.SUPPLIER,
            original_filename="suppliers.csv",
            content_type="text/csv",
            file_bytes=data,
        )
        await async_session.commit()
        job = await import_service.run_validation(async_session, tenant_id="tenant-svc-1", job_id=job.id)
        assert job.status == ImportStatus.DRY_RUN_READY
        assert job.total_rows == 5
        assert job.valid_rows == 5
        assert job.invalid_rows == 0

    async def test_dry_run_mixed(self, async_session: AsyncSession) -> None:
        data = (FIXTURES / "suppliers_mixed.csv").read_bytes()
        job = await import_service.create_import_job(
            async_session,
            tenant_id="tenant-svc-2",
            entity_type=ImportEntityType.SUPPLIER,
            original_filename="mixed.csv",
            content_type="text/csv",
            file_bytes=data,
        )
        await async_session.commit()
        job = await import_service.run_validation(async_session, tenant_id="tenant-svc-2", job_id=job.id)
        assert job.status == ImportStatus.DRY_RUN_READY
        assert job.total_rows == 5
        assert job.invalid_rows >= 3  # bad fein, missing name, bad state

    async def test_missing_columns_fails(self, async_session: AsyncSession) -> None:
        data = (FIXTURES / "suppliers_missing_columns.csv").read_bytes()
        job = await import_service.create_import_job(
            async_session,
            tenant_id="t-mc",
            entity_type=ImportEntityType.SUPPLIER,
            original_filename="mc.csv",
            content_type="text/csv",
            file_bytes=data,
        )
        await async_session.commit()
        job = await import_service.run_validation(async_session, tenant_id="t-mc", job_id=job.id)
        assert job.status == ImportStatus.FAILED

    async def test_too_many_rows(self, async_session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(import_service.settings, "import_max_rows", 2)
        text = "name,fein,state\r\n" + "\r\n".join(f"R{i},12-345678{i % 10}," "CA" for i in range(10))
        job = await import_service.create_import_job(
            async_session,
            tenant_id="t-big",
            entity_type=ImportEntityType.SUPPLIER,
            original_filename="big.csv",
            content_type="text/csv",
            file_bytes=text.encode("utf-8"),
        )
        await async_session.commit()
        job = await import_service.run_validation(async_session, tenant_id="t-big", job_id=job.id)
        assert job.status == ImportStatus.FAILED

    async def test_commit_happy(self, async_session: AsyncSession) -> None:
        data = (FIXTURES / "suppliers_valid.csv").read_bytes()
        job = await import_service.create_import_job(
            async_session,
            tenant_id="tenant-commit-1",
            entity_type=ImportEntityType.SUPPLIER,
            original_filename="suppliers.csv",
            content_type="text/csv",
            file_bytes=data,
        )
        await async_session.commit()
        await import_service.run_validation(async_session, tenant_id="tenant-commit-1", job_id=job.id)
        await async_session.commit()

        job = await import_service.run_commit(tenant_id="tenant-commit-1", job_id=job.id)
        assert job.status == ImportStatus.COMPLETED
        assert job.imported_rows == 5

        # New session so we observe the committed rows
        import app.db as _db

        async with _db.AsyncSessionLocal() as s:
            count = await s.scalar(
                select(__import__("sqlalchemy").func.count(Supplier.id)).where(Supplier.tenant_id == "tenant-commit-1")
            )
            assert count == 5

    async def test_dedupe_in_file(self, async_session: AsyncSession) -> None:
        data = (FIXTURES / "suppliers_duplicate.csv").read_bytes()
        job = await import_service.create_import_job(
            async_session,
            tenant_id="t-dup",
            entity_type=ImportEntityType.SUPPLIER,
            original_filename="dup.csv",
            content_type="text/csv",
            file_bytes=data,
        )
        await async_session.commit()
        job = await import_service.run_validation(async_session, tenant_id="t-dup", job_id=job.id)
        # First row counts as valid; second is flagged duplicate_fein_in_file
        assert job.valid_rows == 1
        assert job.invalid_rows == 1

    async def test_cancel(self, async_session: AsyncSession) -> None:
        data = (FIXTURES / "suppliers_valid.csv").read_bytes()
        job = await import_service.create_import_job(
            async_session,
            tenant_id="t-c",
            entity_type=ImportEntityType.SUPPLIER,
            original_filename="x.csv",
            content_type="text/csv",
            file_bytes=data,
        )
        canceled = await import_service.cancel_job(async_session, tenant_id="t-c", job_id=job.id)
        assert canceled.status == ImportStatus.CANCELED
        with pytest.raises(import_service.InvalidTransitionError):
            await import_service.cancel_job(async_session, tenant_id="t-c", job_id=job.id)

    async def test_invalid_transition_commit_from_pending(self, async_session: AsyncSession) -> None:
        data = (FIXTURES / "suppliers_valid.csv").read_bytes()
        job = await import_service.create_import_job(
            async_session,
            tenant_id="t-it",
            entity_type=ImportEntityType.SUPPLIER,
            original_filename="x.csv",
            content_type="text/csv",
            file_bytes=data,
        )
        await async_session.commit()
        with pytest.raises(import_service.InvalidTransitionError):
            await import_service.run_commit(tenant_id="t-it", job_id=job.id)

    def test_sanitize_filename(self) -> None:
        assert import_service.sanitize_filename("../../etc/passwd") == "passwd"
        assert import_service.sanitize_filename("a b/c\\d.csv") == "d.csv"
        assert import_service.sanitize_filename("") == "upload"

    def test_stream_errors_csv(self) -> None:
        errs = [
            ImportRowError(
                import_job_id="j",
                row_number=2,
                column="fein",
                value="bad,val\n",
                error_code="fein_format",
                error_message="Bad",
            )
        ]
        body = "".join(import_service.stream_errors_csv(errs))
        # First row is header
        reader = csv.reader(io.StringIO(body))
        rows = list(reader)
        assert rows[0] == [
            "row_number",
            "column",
            "value",
            "error_code",
            "error_message",
        ]
        assert rows[1][2] == "bad,val\n"


# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------


class TestImportsApi:
    async def _upload(
        self,
        client: AsyncClient,
        *,
        filename: str = "suppliers.csv",
        content: bytes | None = None,
        entity_type: str = "supplier",
        mapping: dict[str, str] | None = None,
        on_duplicate: str = "error",
    ) -> dict[str, Any]:
        data = content if content is not None else (FIXTURES / "suppliers_valid.csv").read_bytes()
        files = {"file": (filename, data, "text/csv")}
        form: dict[str, str] = {
            "entity_type": entity_type,
            "on_duplicate": on_duplicate,
        }
        if mapping is not None:
            form["mapping"] = json.dumps(mapping)
        resp = await client.post("/v1/imports", files=files, data=form)
        return (
            resp.json()
            if resp.headers.get("content-type", "").startswith("application/json")
            else {"_status": resp.status_code, "_text": resp.text}
        )

    async def test_upload_dry_run(self, auth_client: tuple[AsyncClient, Any]) -> None:
        client, _ = auth_client
        body = await self._upload(client)
        assert body.get("status") == "dry_run_ready"
        assert body["total_rows"] == 5
        assert body["valid_rows"] == 5

    async def test_upload_bad_extension(self, auth_client: tuple[AsyncClient, Any]) -> None:
        client, _ = auth_client
        resp = await client.post(
            "/v1/imports",
            files={"file": ("x.pdf", b"hello", "application/pdf")},
            data={"entity_type": "supplier"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "unsupported_format"

    async def test_list_and_get(self, auth_client: tuple[AsyncClient, Any]) -> None:
        client, _ = auth_client
        created = await self._upload(client)
        list_resp = await client.get("/v1/imports")
        assert list_resp.status_code == 200
        assert any(item["id"] == created["id"] for item in list_resp.json())
        detail = await client.get(f"/v1/imports/{created['id']}")
        assert detail.status_code == 200
        body = detail.json()
        assert body["id"] == created["id"]
        assert "errors_preview" in body

    async def test_commit_happy(self, auth_client: tuple[AsyncClient, Any]) -> None:
        client, _ = auth_client
        created = await self._upload(client)
        resp = await client.post(f"/v1/imports/{created['id']}/commit", json={"confirmed": True})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "completed"
        assert body["imported_rows"] == 5

    async def test_commit_requires_confirmation(self, auth_client: tuple[AsyncClient, Any]) -> None:
        client, _ = auth_client
        created = await self._upload(client)
        resp = await client.post(f"/v1/imports/{created['id']}/commit", json={"confirmed": False})
        assert resp.status_code == 400

    async def test_errors_csv_download(self, auth_client: tuple[AsyncClient, Any]) -> None:
        client, _ = auth_client
        created = await self._upload(client, content=(FIXTURES / "suppliers_mixed.csv").read_bytes())
        resp = await client.get(f"/v1/imports/{created['id']}/errors.csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "row_number" in resp.text

    async def test_template_and_columns(self, auth_client: tuple[AsyncClient, Any]) -> None:
        client, _ = auth_client
        cols = await client.get("/v1/imports/columns/supplier")
        assert cols.status_code == 200
        names = {c["field"] for c in cols.json()["columns"]}
        assert {"name", "fein", "state"}.issubset(names)
        tpl = await client.get("/v1/imports/template/supplier")
        assert tpl.status_code == 200
        assert "name,fein,state" in tpl.text.lower()

    async def test_cross_tenant_404(self, auth_client: tuple[AsyncClient, Any], client: AsyncClient) -> None:
        owner_client, _ = auth_client
        created = await self._upload(owner_client)
        # Register a second tenant via the shared `client` (no auth header)
        resp = await client.post(
            "/v1/auth/register",
            json={
                "email": "other@example.com",
                "password": "Otra-Pass-1!",
                "full_name": "Other",
                "tenant_name": "Other Co",
            },
        )
        assert resp.status_code == 201
        token = resp.json()["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"
        try:
            cross = await client.get(f"/v1/imports/{created['id']}")
            assert cross.status_code == 404
        finally:
            client.headers.pop("Authorization", None)

    async def test_cancel(self, auth_client: tuple[AsyncClient, Any]) -> None:
        client, _ = auth_client
        created = await self._upload(client)
        # Job is now DRY_RUN_READY — cancel is allowed
        resp = await client.post(f"/v1/imports/{created['id']}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "canceled"

    async def test_unknown_entity_type(self, auth_client: tuple[AsyncClient, Any]) -> None:
        client, _ = auth_client
        resp = await client.get("/v1/imports/columns/widgets")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Celery task wrapper (eager-mode)
# ---------------------------------------------------------------------------


class TestImportTasks:
    async def test_task_validates_pending(self, async_session: AsyncSession) -> None:
        from app.workers.tasks.import_tasks import process_import_job

        data = (FIXTURES / "suppliers_valid.csv").read_bytes()
        job = await import_service.create_import_job(
            async_session,
            tenant_id="t-task-1",
            entity_type=ImportEntityType.SUPPLIER,
            original_filename="x.csv",
            content_type="text/csv",
            file_bytes=data,
        )
        await async_session.commit()
        result = await asyncio.to_thread(lambda: process_import_job.apply(args=[job.id]).get())
        assert result["status"] == "dry_run_ready"

    async def test_task_commits_dry_run_ready(self, async_session: AsyncSession) -> None:
        from app.workers.tasks.import_tasks import process_import_job

        data = (FIXTURES / "suppliers_valid.csv").read_bytes()
        job = await import_service.create_import_job(
            async_session,
            tenant_id="t-task-2",
            entity_type=ImportEntityType.SUPPLIER,
            original_filename="x.csv",
            content_type="text/csv",
            file_bytes=data,
        )
        await async_session.commit()
        await import_service.run_validation(async_session, tenant_id="t-task-2", job_id=job.id)
        await async_session.commit()
        result = await asyncio.to_thread(lambda: process_import_job.apply(args=[job.id]).get())
        assert result["status"] == "completed"
        assert result["imported_rows"] == 5

    async def test_task_missing_job(self, async_session: AsyncSession) -> None:
        from app.workers.tasks.import_tasks import process_import_job

        result = await asyncio.to_thread(lambda: process_import_job.apply(args=["no-such-id"]).get())
        assert result["status"] == "not_found"

    async def test_task_skips_terminal(self, async_session: AsyncSession) -> None:
        from app.workers.tasks.import_tasks import process_import_job

        data = (FIXTURES / "suppliers_valid.csv").read_bytes()
        job = await import_service.create_import_job(
            async_session,
            tenant_id="t-task-3",
            entity_type=ImportEntityType.SUPPLIER,
            original_filename="x.csv",
            content_type="text/csv",
            file_bytes=data,
        )
        await import_service.cancel_job(async_session, tenant_id="t-task-3", job_id=job.id)
        await async_session.commit()
        result = await asyncio.to_thread(lambda: process_import_job.apply(args=[job.id]).get())
        assert result.get("skipped") is True


# ---------------------------------------------------------------------------
# Importer registry
# ---------------------------------------------------------------------------


def test_get_importer_returns_supplier_importer() -> None:
    imp = get_importer(ImportEntityType.SUPPLIER)
    assert isinstance(imp, SupplierImporter)
