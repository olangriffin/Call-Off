from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DeliverableBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    reference: str = Field(
        min_length=1,
        max_length=150,
    )
    name: str = Field(
        min_length=1,
        max_length=250,
    )
    deliverable_type: str = Field(
        min_length=1,
        max_length=100,
    )
    description: str | None = None
    status: str = Field(
        default="not_started",
        min_length=1,
        max_length=30,
    )
    planned_issue_date: date | None = None
    required_approval_date: date | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> "DeliverableBase":
        if (
            self.planned_issue_date is not None
            and self.required_approval_date is not None
            and self.required_approval_date < self.planned_issue_date
        ):
            raise ValueError(
                "required_approval_date cannot be earlier than planned_issue_date."
            )

        return self


class DeliverableCreate(DeliverableBase):
    pass


class DeliverableUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    reference: str | None = Field(
        default=None,
        min_length=1,
        max_length=150,
    )
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=250,
    )
    deliverable_type: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    description: str | None = None
    status: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
    )
    planned_issue_date: date | None = None
    required_approval_date: date | None = None


class DeliverableRead(DeliverableBase):
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )

    id: uuid.UUID
    work_package_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
