from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.consent import ConsentScope

__all__ = ["ConsentRead", "ConsentList"]


class ConsentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    supplier_id: str
    scope: ConsentScope
    portal_ids_json: list[str]
    granted_at: datetime
    revoked_at: datetime | None = None
    granted_by_user_id: str
    signed_text: str
    signature_b64: str
    created_at: datetime
    updated_at: datetime


class ConsentList(BaseModel):
    items: list[ConsentRead]
    total: int
    limit: int
    offset: int
