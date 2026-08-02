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
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.backend.database.base import Base

if TYPE_CHECKING:
    from app.backend.models.package.revision import DeliverableRevision


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    revision_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("deliverable_revisions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    approval_stage: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="external_review",
        server_default="external_review",
    )

    reviewer_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    submitted_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    response_due_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    response_received_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    comments: Mapped[str | None] = mapped_column(
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

    revision: Mapped[DeliverableRevision] = relationship(
        back_populates="approvals",
    )
