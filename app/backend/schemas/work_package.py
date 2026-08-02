from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WorkPackageBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    package_type: str | None = Field(default=None, max_length=100)
    description: str | None = None
    status: str = Field(default="active", min_length=1, max_length=30)
    planned_start: date | None = None
    planned_finish: date | None = None
    required_on_site_date: date | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> "WorkPackageBase":
        if (
            self.planned_start is not None
            and self.planned_finish is not None
            and self.planned_finish < self.planned_start
        ):
            raise ValueError(
                "planned_finish cannot be earlier than planned_start."
            )

        return self


class WorkPackageCreate(WorkPackageBase):
    pass


class WorkPackageUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    package_type: str | None = Field(default=None, max_length=100)
    description: str | None = None
    status: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
    )
    planned_start: date | None = None
    planned_finish: date | None = None
    required_on_site_date: date | None = None


class WorkPackageRead(WorkPackageBase):
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )

    id: uuid.UUID
    project_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
