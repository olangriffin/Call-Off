from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProjectBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    client_name: str | None = Field(default=None, max_length=200)
    status: str = Field(default="active", min_length=1, max_length=30)
    planned_start: date | None = None
    planned_finish: date | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> "ProjectBase":
        if (
            self.planned_start is not None
            and self.planned_finish is not None
            and self.planned_finish < self.planned_start
        ):
            raise ValueError(
                "planned_finish cannot be earlier than planned_start."
            )

        return self


class ProjectCreate(ProjectBase):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    client_name: str | None = Field(default=None, max_length=200)
    status: str | None = Field(default=None, min_length=1, max_length=30)
    planned_start: date | None = None
    planned_finish: date | None = None


class ProjectRead(ProjectBase):
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )

    id: uuid.UUID
    organization_id: str
    created_at: datetime
    updated_at: datetime
