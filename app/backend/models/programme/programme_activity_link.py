from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.backend.database.base import Base

if TYPE_CHECKING:
    from app.backend.models.programme.programme_activity import ProgrammeActivity


class ProgrammeActivityLink(Base):
    __tablename__ = "programme_activity_links"

    __table_args__ = (
        UniqueConstraint(
            "source_activity_id",
            "target_activity_id",
            name="uq_programme_activity_link",
        ),
        CheckConstraint(
            "source_activity_id <> target_activity_id",
            name="ck_programme_activity_link_not_self",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    source_activity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("programme_activities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    target_activity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("programme_activities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    source_activity: Mapped[ProgrammeActivity] = relationship(
        foreign_keys=[source_activity_id],
        back_populates="source_alignment_links",
    )

    target_activity: Mapped[ProgrammeActivity] = relationship(
        foreign_keys=[target_activity_id],
        back_populates="target_alignment_links",
    )
