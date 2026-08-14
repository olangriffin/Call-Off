from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
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
    from app.backend.models.programme.programme_calendar import ProgrammeCalendar
    from app.backend.models.programme.programme_baseline import ProgrammeBaseline
    from app.backend.models.programme.programme_import import ProgrammeImport
    from app.backend.models.programme.programme_revision import ProgrammeRevision
    from app.backend.models.project import Project


class Programme(Base):
    __tablename__ = "programmes"

    __table_args__ = (
        CheckConstraint(
            "programme_type IN ('client', 'internal')",
            name="ck_programmes_type",
        ),
        UniqueConstraint(
            "project_id",
            "programme_type",
            name="uq_programmes_project_type",
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

    programme_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="internal",
        server_default="internal",
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        default="Project Programme",
        server_default="Project Programme",
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
        back_populates="programmes",
    )

    revisions: Mapped[list[ProgrammeRevision]] = relationship(
        back_populates="programme",
        cascade="all, delete-orphan",
    )
    baselines: Mapped[list[ProgrammeBaseline]] = relationship(
        back_populates="programme",
        cascade="all, delete-orphan",
    )

    imports: Mapped[list[ProgrammeImport]] = relationship(
        back_populates="programme",
        cascade="all, delete-orphan",
    )

    calendars: Mapped[list[ProgrammeCalendar]] = relationship(
        back_populates="programme",
        cascade="all, delete-orphan",
    )
