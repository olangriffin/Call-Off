from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.backend.database.base import Base

if TYPE_CHECKING:
    from app.backend.models.programme.programme_activity import ProgrammeActivity


class ProgrammeDependency(Base):
    __tablename__ = "programme_dependencies"

    __table_args__ = (
        UniqueConstraint(
            "predecessor_id",
            "successor_id",
            "dependency_type",
            name="uq_programme_dependency",
        ),
        CheckConstraint(
            "predecessor_id <> successor_id",
            name="ck_programme_dependency_not_self",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    predecessor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("programme_activities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    successor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("programme_activities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    dependency_type: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
        default="FS",
        server_default="FS",
    )

    lag_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    predecessor: Mapped[ProgrammeActivity] = relationship(
        foreign_keys=[predecessor_id],
        back_populates="successor_dependencies",
    )

    successor: Mapped[ProgrammeActivity] = relationship(
        foreign_keys=[successor_id],
        back_populates="predecessor_dependencies",
    )
