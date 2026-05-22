"""L3.7 — Supplier importer.

Translates a single CSV/XLSX row into a :class:`~app.models.Supplier`
INSERT (or UPDATE, when the operator passes ``on_duplicate=update``).

Required source columns (one of the listed aliases must be present):

* ``name`` — aliases ``company``, ``supplier``, ``supplier_name``,
  ``account_name``. Maps to ``Supplier.legal_name``.
* ``fein`` — aliases ``ein``, ``tax_id``, ``federal_id``. Stored as
  ``Supplier.ein`` after normalisation to ``XX-XXXXXXX``.
* ``state`` — alias ``primary_state``. Stored inside
  ``Supplier.address_json`` under ``"state"`` (the Supplier model uses a
  JSON address blob, not a flat column).

Validation error codes are deliberately stable strings — the UI maps
them to localised messages and downstream automation can branch on them
without parsing English text.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Supplier
from app.services.importers.base import (
    BaseImporter,
    ColumnSpec,
    RowError,
    ValidatedRow,
)

__all__ = ["SupplierImporter", "normalize_fein", "ImportSupplierRowSchema"]


# ---------------------------------------------------------------------------
# Column metadata (drives the UI mapper + template generator)
# ---------------------------------------------------------------------------

_COLUMNS: tuple[ColumnSpec, ...] = (
    ColumnSpec(
        field="name",
        required=True,
        aliases=("company", "supplier", "supplier_name", "account_name", "legal_name"),
        description="Supplier legal name.",
        example="Acme Trucking LLC",
    ),
    ColumnSpec(
        field="fein",
        required=True,
        aliases=("ein", "tax_id", "federal_id"),
        description="Federal EIN, format XX-XXXXXXX.",
        example="12-3456789",
    ),
    ColumnSpec(
        field="state",
        required=True,
        aliases=("primary_state",),
        description="2-letter US state code.",
        example="CA",
    ),
    ColumnSpec(
        field="email",
        required=False,
        aliases=("primary_email", "contact_email"),
        description="Primary email contact.",
        example="ops@acme.example",
    ),
    ColumnSpec(
        field="phone",
        required=False,
        aliases=("primary_phone", "contact_phone"),
        description="Primary phone (any format).",
        example="(555) 123-4567",
    ),
    ColumnSpec(
        field="address_line1",
        required=False,
        aliases=("address1", "street", "street1"),
        description="Street address line 1.",
    ),
    ColumnSpec(
        field="address_line2",
        required=False,
        aliases=("address2", "street2"),
        description="Street address line 2.",
    ),
    ColumnSpec(
        field="city",
        required=False,
        aliases=("town",),
        description="City.",
    ),
    ColumnSpec(
        field="zip",
        required=False,
        aliases=("postal_code", "zipcode", "zip_code"),
        description="ZIP / postal code.",
    ),
    ColumnSpec(
        field="naic_code",
        required=False,
        aliases=("naics", "naics_code", "naic"),
        description="NAICS industry code.",
    ),
    ColumnSpec(
        field="gwp_band",
        required=False,
        aliases=("premium_band", "size_band"),
        description="Free-form GWP / premium tier band.",
    ),
    ColumnSpec(
        field="notes",
        required=False,
        aliases=("comments", "memo"),
        description="Free-form internal notes.",
    ),
)


# ---------------------------------------------------------------------------
# Normalisers
# ---------------------------------------------------------------------------

_FEIN_DIGITS = re.compile(r"\D+")
_FEIN_FMT = re.compile(r"^\d{2}-\d{7}$")
_US_STATES: frozenset[str] = frozenset(
    {
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
        "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
        "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
        "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
        "WI", "WY", "DC", "PR", "GU", "VI", "AS", "MP",
    }
)


def normalize_fein(raw: str) -> str | None:
    """Return ``XX-XXXXXXX`` or ``None`` if not 9 digits.

    Strips every non-digit (whitespace, dashes, parens, ``.`` etc.) and
    reformats. We tolerate sources that store the EIN as a plain 9-digit
    number ("123456789") since that's what Excel does when it strips
    leading zeros.
    """

    if not raw:
        return None
    digits = _FEIN_DIGITS.sub("", str(raw))
    if len(digits) != 9 or not digits.isdigit():
        return None
    return f"{digits[:2]}-{digits[2:]}"


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


# ---------------------------------------------------------------------------
# Per-row Pydantic schema (just used for email validation right now —
# format-level rules live below)
# ---------------------------------------------------------------------------


class ImportSupplierRowSchema(BaseModel):
    """Strict per-row schema used to surface ``email_invalid`` codes."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=64)
    address_line1: str | None = Field(default=None, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=128)
    zip: str | None = Field(default=None, max_length=32)
    naic_code: str | None = Field(default=None, max_length=16)
    gwp_band: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=2000)


# ---------------------------------------------------------------------------
# Importer
# ---------------------------------------------------------------------------


class SupplierImporter(BaseImporter):
    entity_type = "supplier"
    columns = _COLUMNS

    # ----- validation -----------------------------------------------------

    def validate_row(self, row: dict[str, str], row_number: int) -> ValidatedRow:
        errors: list[RowError] = []
        name = _clean(row.get("name"))
        raw_fein = _clean(row.get("fein"))
        raw_state = _clean(row.get("state"))

        if not name:
            errors.append(
                RowError(
                    row_number=row_number,
                    column="name",
                    value=name,
                    error_code="name_required",
                    error_message="Supplier name is required.",
                )
            )
        elif len(name) > 255:
            errors.append(
                RowError(
                    row_number=row_number,
                    column="name",
                    value=name[:200],
                    error_code="name_too_long",
                    error_message="Supplier name must be 255 characters or fewer.",
                )
            )

        fein_norm: str | None = None
        if not raw_fein:
            errors.append(
                RowError(
                    row_number=row_number,
                    column="fein",
                    value=raw_fein,
                    error_code="fein_required",
                    error_message="FEIN is required.",
                )
            )
        else:
            fein_norm = normalize_fein(raw_fein)
            if not fein_norm or not _FEIN_FMT.match(fein_norm):
                errors.append(
                    RowError(
                        row_number=row_number,
                        column="fein",
                        value=raw_fein,
                        error_code="fein_format",
                        error_message=(
                            "FEIN must be 9 digits, format XX-XXXXXXX "
                            "(e.g. 12-3456789)."
                        ),
                    )
                )

        state_norm: str | None = None
        if not raw_state:
            errors.append(
                RowError(
                    row_number=row_number,
                    column="state",
                    value=raw_state,
                    error_code="state_required",
                    error_message="Primary state is required.",
                )
            )
        else:
            state_norm = raw_state.upper()
            if len(state_norm) != 2 or state_norm not in _US_STATES:
                errors.append(
                    RowError(
                        row_number=row_number,
                        column="state",
                        value=raw_state,
                        error_code="state_invalid",
                        error_message="State must be a valid 2-letter US state code.",
                    )
                )
                state_norm = None

        # Optional fields → Pydantic for email + length caps
        optional_payload = {
            k: row.get(k)
            for k in (
                "email",
                "phone",
                "address_line1",
                "address_line2",
                "city",
                "zip",
                "naic_code",
                "gwp_band",
                "notes",
            )
            if row.get(k) not in (None, "")
        }
        validated_optional: dict[str, Any] = {}
        try:
            schema = ImportSupplierRowSchema.model_validate(optional_payload)
            validated_optional = schema.model_dump(exclude_none=True)
        except ValidationError as exc:
            for err in exc.errors():
                loc = err.get("loc") or ("",)
                col = str(loc[0]) if loc else ""
                code = self._pydantic_code(col, str(err.get("type") or ""))
                errors.append(
                    RowError(
                        row_number=row_number,
                        column=col or None,
                        value=str(row.get(col, ""))[:200] if col else None,
                        error_code=code,
                        error_message=str(err.get("msg") or "Invalid value."),
                    )
                )

        if errors:
            return ValidatedRow(row_number=row_number, errors=errors)

        data: dict[str, Any] = {
            "legal_name": name,
            "ein": fein_norm,
        }
        if validated_optional.get("email"):
            data["primary_email"] = validated_optional["email"]
        if validated_optional.get("phone"):
            data["primary_phone"] = validated_optional["phone"]
        if validated_optional.get("naic_code"):
            data["naics_code"] = validated_optional["naic_code"]

        address: dict[str, str] = {}
        if validated_optional.get("address_line1"):
            address["line1"] = validated_optional["address_line1"]
        if validated_optional.get("address_line2"):
            address["line2"] = validated_optional["address_line2"]
        if validated_optional.get("city"):
            address["city"] = validated_optional["city"]
        if state_norm:
            address["state"] = state_norm
        if validated_optional.get("zip"):
            address["postal_code"] = validated_optional["zip"]
        if address:
            data["address_json"] = address

        # Stash non-model extras so callers (or future schema upgrades)
        # can audit-log them without re-parsing the file.
        extras: dict[str, Any] = {}
        if validated_optional.get("gwp_band"):
            extras["gwp_band"] = validated_optional["gwp_band"]
        if validated_optional.get("notes"):
            extras["notes"] = validated_optional["notes"]
        if extras:
            data["_extras"] = extras

        return ValidatedRow(
            row_number=row_number,
            data=data,
            dedupe_key=fein_norm,
        )

    @staticmethod
    def _pydantic_code(column: str, pyd_type: str) -> str:
        if column == "email":
            return "email_invalid"
        if "max_length" in pyd_type or "string_too_long" in pyd_type:
            return f"{column}_too_long" if column else "value_too_long"
        return f"{column}_invalid" if column else "value_invalid"

    # ----- DB hooks --------------------------------------------------------

    async def existing_dedupe_keys(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        keys: list[str],
    ) -> set[str]:
        if not keys:
            return set()
        stmt = select(Supplier.ein).where(
            Supplier.tenant_id == tenant_id,
            Supplier.ein.in_(keys),
        )
        result = await session.execute(stmt)
        return {row[0] for row in result.all() if row[0] is not None}

    async def insert_batch(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        rows: list[ValidatedRow],
        on_duplicate: str,
    ) -> dict[str, int]:
        counts = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        if not rows:
            return counts

        keys = [r.dedupe_key for r in rows if r.dedupe_key]
        existing = await self.existing_dedupe_keys(
            session, tenant_id=tenant_id, keys=keys
        )

        # Pre-fetch all existing rows in one shot for the update path.
        existing_models: dict[str, Supplier] = {}
        if existing and on_duplicate == "update":
            stmt = select(Supplier).where(
                Supplier.tenant_id == tenant_id,
                Supplier.ein.in_(list(existing)),
            )
            result = await session.execute(stmt)
            for sup in result.scalars().all():
                if sup.ein:
                    existing_models[sup.ein] = sup

        for row in rows:
            if not row.data:
                counts["errors"] += 1
                continue
            data = {k: v for k, v in row.data.items() if not k.startswith("_")}
            key = row.dedupe_key
            if key and key in existing:
                if on_duplicate == "update":
                    sup = existing_models.get(key)
                    if sup is None:
                        # Fall back to a one-off fetch (cheap, rare).
                        result = await session.execute(
                            select(Supplier).where(
                                Supplier.tenant_id == tenant_id,
                                Supplier.ein == key,
                            )
                        )
                        sup = result.scalar_one_or_none()
                    if sup is not None:
                        for field_, value in data.items():
                            setattr(sup, field_, value)
                        counts["updated"] += 1
                        continue
                if on_duplicate == "skip":
                    counts["skipped"] += 1
                    continue
                # on_duplicate == "error" — caller should have surfaced
                # duplicate_fein_existing already, but guard belt-and-
                # braces here.
                counts["errors"] += 1
                continue
            session.add(Supplier(tenant_id=tenant_id, **data))
            counts["inserted"] += 1

        await session.flush()
        return counts
