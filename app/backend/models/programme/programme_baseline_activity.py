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
    UniqueConstraint,
    Uuid,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.backend.database.base import Base

if TYPE_CHECKING:
    from app.backend.models.package.package import WorkPackage
    from app.backend.models.programme.programme_activity import ProgrammeActivity
    from app.backend.models.programme.programme_baseline import ProgrammeBaseline


class ProgrammeBaselineActivity(Base):
    __tablename__ = "programme_baseline_activities"

    __table_args__ = (
        UniqueConstraint(
            "baseline_id",
            "activity_code",
            name="uq_baseline_activity_code",
        ),
        CheckConstraint(
            "percent_complete >= 0 AND percent_complete <= 100",
            name="ck_baseline_activity_percent_complete",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    baseline_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("programme_baselines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source_activity_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("programme_activities.id", ondelete="SET NULL"),
        nullable=True,
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

    external_id: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    work_package_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    work_package_name: Mapped[str | None] = mapped_column(
        String(200),
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

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    baseline: Mapped[ProgrammeBaseline] = relationship(
        back_populates="activities",
    )

    source_activity: Mapped[ProgrammeActivity | None] = relationship()

    work_package: Mapped[WorkPackage | None] = relationship()
