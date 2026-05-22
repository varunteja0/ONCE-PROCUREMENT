"""L3.7 — Per-row import validation error.

Children of :class:`~app.models.import_job.ImportJob`. We persist the
errors instead of recomputing on demand because the dry-run / commit
gap can span hours: the operator may need to re-export the report
later (e.g. to send back to the data owner so they can clean the
source spreadsheet).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, _uuid

__all__ = ["ImportRowError"]


# Cap stored value to keep the table tidy even if someone pastes a 1MB
# cell. The UI never needs the full value to explain a typo.
_VALUE_MAX_LEN = 200


class ImportRowError(Base):
    __tablename__ = "import_row_errors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    import_job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("import_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    column: Mapped[str | None] = mapped_column(String(128), nullable=True)
    value: Mapped[str | None] = mapped_column(String(_VALUE_MAX_LEN), nullable=True)
    error_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    error_message: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    @staticmethod
    def truncate_value(raw: object | None) -> str | None:
        """Coerce + cap a cell value for safe persistence."""

        if raw is None:
            return None
        text = str(raw)
        if len(text) <= _VALUE_MAX_LEN:
            return text
        return text[: _VALUE_MAX_LEN - 1] + "…"
