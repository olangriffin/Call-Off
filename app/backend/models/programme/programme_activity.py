from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.backend.database.base import Base
from app.backend.models.programme.programme_calendar import ProgrammeCalendar

if TYPE_CHECKING:
    from app.backend.models.package.package import WorkPackage
    from app.backend.models.programme.programme_dependency import ProgrammeDependency
    from app.backend.models.programme.programme_revision import ProgrammeRevision


class ProgrammeActivity(Base):
    __tablename__ = "programme_activities"

    __table_args__ = (
        UniqueConstraint(
            "programme_revision_id",
            "activity_code",
            name="uq_programme_activity_revision_code",
        ),
        CheckConstraint(
            "percent_complete >= 0 AND percent_complete <= 100",
            name="ck_programme_activity_percent_complete",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    programme_revision_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("programme_revisions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    work_package_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("work_packages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    activity_code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(250),
        nullable=False,
    )

    activity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="task",
        server_default="task",
    )

    external_id: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    planned_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    planned_finish: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    duration_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    percent_complete: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    is_milestone: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="not_started",
        server_default="not_started",
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

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    programme_revision: Mapped[ProgrammeRevision] = relationship(
        back_populates="activities",
    )

    work_package: Mapped[WorkPackage | None] = relationship(
        back_populates="programme_activities",
    )

    predecessor_dependencies: Mapped[list[ProgrammeDependency]] = relationship(
        foreign_keys="ProgrammeDependency.successor_id",
        back_populates="successor",
        cascade="all, delete-orphan",
    )

    successor_dependencies: Mapped[list[ProgrammeDependency]] = relationship(
        foreign_keys="ProgrammeDependency.predecessor_id",
        back_populates="predecessor",
        cascade="all, delete-orphan",
    )

    calendar_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "programme_calendars.id",
            name="fk_programme_activities_calendar_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    programme_calendar: Mapped[ProgrammeCalendar | None] = relationship(
        back_populates="activities",
    )

    parent_activity_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "programme_activities.id",
            name="fk_programme_activities_parent_id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )

    is_summary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )

    parent_activity: Mapped["ProgrammeActivity | None"] = relationship(
        remote_side="ProgrammeActivity.id",
        back_populates="child_activities",
    )

    child_activities: Mapped[list["ProgrammeActivity"]] = relationship(
        back_populates="parent_activity",
    )
