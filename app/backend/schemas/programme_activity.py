from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProgrammeActivityBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    activity_code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=250)
    activity_type: str = Field(default="task", min_length=1, max_length=50)
    work_package_id: uuid.UUID | None = None
    parent_activity_id: uuid.UUID | None = None
    planned_start: datetime | None = None
    planned_finish: datetime | None = None
    is_milestone: bool = False
    status: str = Field(default="not_started", min_length=1, max_length=30)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> ProgrammeActivityBase:
        if (
            self.planned_start is not None
            and self.planned_finish is not None
            and self.planned_finish < self.planned_start
        ):
            raise ValueError("planned_finish cannot be earlier than planned_start.")

        return self


class ProgrammeActivityCreate(ProgrammeActivityBase):
    pass


class ProgrammeActivityUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    activity_code: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=250)
    activity_type: str | None = Field(default=None, min_length=1, max_length=50)
    work_package_id: uuid.UUID | None = None
    parent_activity_id: uuid.UUID | None = None
    planned_start: datetime | None = None
    planned_finish: datetime | None = None
    is_milestone: bool | None = None
    status: str | None = Field(default=None, min_length=1, max_length=30)
    notes: str | None = None


class ProgrammeActivityRead(ProgrammeActivityBase):
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )

    id: uuid.UUID
    programme_revision_id: uuid.UUID
    is_summary: bool
    percent_complete: int
    created_at: datetime
    updated_at: datetime
