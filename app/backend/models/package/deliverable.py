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
    from app.backend.models.package.package import WorkPackage
    from app.backend.models.package.revision import DeliverableRevision


class Deliverable(Base):
    __tablename__ = "deliverables"

    __table_args__ = (
        UniqueConstraint(
            "work_package_id",
            "reference",
            name="uq_deliverables_package_reference",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    work_package_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("work_packages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    reference: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(250),
        nullable=False,
    )

    deliverable_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="not_started",
        server_default="not_started",
    )

    planned_issue_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    required_approval_date: Mapped[date | None] = mapped_column(
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

    work_package: Mapped[WorkPackage] = relationship(
        back_populates="deliverables",
    )

    revisions: Mapped[list[DeliverableRevision]] = relationship(
        back_populates="deliverable",
        cascade="all, delete-orphan",
    )
