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
    from app.backend.models.package.approval import Approval
    from app.backend.models.package.deliverable import Deliverable


class DeliverableRevision(Base):
    __tablename__ = "deliverable_revisions"

    __table_args__ = (
        UniqueConstraint(
            "deliverable_id",
            "revision_code",
            name="uq_revision_deliverable_code",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    deliverable_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("deliverables.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    revision_code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="draft",
        server_default="draft",
    )

    issue_purpose: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    issue_date: Mapped[date | None] = mapped_column(
        Date,
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

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    deliverable: Mapped[Deliverable] = relationship(
        back_populates="revisions",
    )

    approvals: Mapped[list[Approval]] = relationship(
        back_populates="revision",
        cascade="all, delete-orphan",
    )
