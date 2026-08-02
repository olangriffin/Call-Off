from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ApprovalBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    approval_stage: str = Field(
        default="external_review",
        min_length=1,
        max_length=100,
    )
    reviewer_name: str | None = Field(
        default=None,
        max_length=200,
    )
    status: str = Field(
        default="pending",
        min_length=1,
        max_length=30,
    )
    submitted_date: date | None = None
    response_due_date: date | None = None
    response_received_date: date | None = None
    comments: str | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "ApprovalBase":
        if (
            self.submitted_date is not None
            and self.response_due_date is not None
            and self.response_due_date < self.submitted_date
        ):
            raise ValueError(
                "response_due_date cannot be earlier than submitted_date."
            )

        if (
            self.submitted_date is not None
            and self.response_received_date is not None
            and self.response_received_date < self.submitted_date
        ):
            raise ValueError(
                "response_received_date cannot be earlier than submitted_date."
            )

        return self


class ApprovalCreate(ApprovalBase):
    pass


class ApprovalUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    approval_stage: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    reviewer_name: str | None = Field(
        default=None,
        max_length=200,
    )
    status: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
    )
    submitted_date: date | None = None
    response_due_date: date | None = None
    response_received_date: date | None = None
    comments: str | None = None


class ApprovalRead(ApprovalBase):
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )

    id: uuid.UUID
    revision_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
