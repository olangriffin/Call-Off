from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class DeliverableRevisionBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    revision_code: str = Field(
        min_length=1,
        max_length=30,
    )
    status: str = Field(
        default="draft",
        min_length=1,
        max_length=30,
    )
    issue_purpose: str | None = Field(
        default=None,
        max_length=50,
    )
    issue_date: date | None = None
    notes: str | None = None


class DeliverableRevisionCreate(DeliverableRevisionBase):
    pass


class DeliverableRevisionUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    revision_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
    )
    status: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
    )
    issue_purpose: str | None = Field(
        default=None,
        max_length=50,
    )
    issue_date: date | None = None
    notes: str | None = None


class DeliverableRevisionRead(DeliverableRevisionBase):
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )

    id: uuid.UUID
    deliverable_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
