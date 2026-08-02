from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.backend.database.base import Base

if TYPE_CHECKING:
    from app.backend.models.programme.programme_calendar import ProgrammeCalendar


class ProgrammeCalendarException(Base):
    __tablename__ = "programme_calendar_exceptions"

    __table_args__ = (
        UniqueConstraint(
            "calendar_id",
            "exception_date",
            name="uq_programme_calendar_exception_date",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    calendar_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("programme_calendars.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    exception_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    exception_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="holiday",
        server_default="holiday",
    )

    is_working_day: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )

    working_periods: Mapped[list[dict] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    calendar: Mapped[ProgrammeCalendar] = relationship(
        back_populates="exceptions",
    )
