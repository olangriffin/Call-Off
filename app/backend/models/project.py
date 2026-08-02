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
    from app.backend.models.organisation import Organisation
    from app.backend.models.package.package import WorkPackage
    from app.backend.models.programme.programme import Programme


class Project(Base):
    __tablename__ = "projects"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "code",
            name="uq_projects_organization_code",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    organization_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("organization.id", ondelete="CASCADE"),
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

    client_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
        server_default="active",
    )

    programme: Mapped[Programme | None] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        uselist=False,
    )

    planned_start: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    planned_finish: Mapped[date | None] = mapped_column(
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

    organisation: Mapped[Organisation] = relationship(
        back_populates="projects",
    )

    work_packages: Mapped[list["WorkPackage"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
