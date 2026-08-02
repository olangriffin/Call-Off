from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.backend.database.base import Base

if TYPE_CHECKING:
    from app.backend.models.programme.programme_calendar_exception import (
        ProgrammeCalendarException,
    )

    from app.backend.models.programme.programme import Programme
    from app.backend.models.programme.programme_activity import ProgrammeActivity


def default_weekly_schedule() -> dict:
    return {
        "monday": [{"start": "08:00", "end": "17:00"}],
        "tuesday": [{"start": "08:00", "end": "17:00"}],
        "wednesday": [{"start": "08:00", "end": "17:00"}],
        "thursday": [{"start": "08:00", "end": "17:00"}],
        "friday": [{"start": "08:00", "end": "17:00"}],
        "saturday": [],
        "sunday": [],
    }


class ProgrammeCalendar(Base):
    __tablename__ = "programme_calendars"

    __table_args__ = (
        UniqueConstraint(
            "programme_id",
            "name",
            name="uq_programme_calendar_name",
        ),
        Index(
            "uq_programme_calendar_default",
            "programme_id",
            unique=True,
            postgresql_where=text("is_default = true"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    programme_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("programmes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    timezone: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="UTC",
        server_default="UTC",
    )

    standard_day_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=480,
        server_default="480",
    )

    weekly_schedule: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=default_weekly_schedule,
    )

    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
        server_default="active",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    programme: Mapped[Programme] = relationship(
        back_populates="calendars",
    )

    exceptions: Mapped[list[ProgrammeCalendarException]] = relationship(
        back_populates="calendar",
        cascade="all, delete-orphan",
    )

    activities: Mapped[list[ProgrammeActivity]] = relationship(
        back_populates="programme_calendar",
    )
