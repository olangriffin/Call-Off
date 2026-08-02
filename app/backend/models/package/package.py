from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.backend.database.base import Base

if TYPE_CHECKING:
    from app.backend.models.package.deliverable import Deliverable
    from app.backend.models.programme.programme_activity import ProgrammeActivity
    from app.backend.models.project import Project


class WorkPackage(Base):
    __tablename__ = "work_packages"

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "code",
            name="uq_work_packages_project_code",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    package_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
        server_default="active",
    )

    planned_start: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    planned_finish: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    required_on_site_date: Mapped[date | None] = mapped_column(
        Date,
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

    project: Mapped[Project] = relationship(
        back_populates="work_packages",
    )

    deliverables: Mapped[list[Deliverable]] = relationship(
        back_populates="work_package",
        cascade="all, delete-orphan",
    )

    programme_activities: Mapped[list[ProgrammeActivity]] = relationship(
        back_populates="work_package",
    )
