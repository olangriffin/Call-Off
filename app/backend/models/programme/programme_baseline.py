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
    from app.backend.models.programme.programme_baseline_activity import (
        ProgrammeBaselineActivity,
    )

    from app.backend.models.programme.programme import Programme
    from app.backend.models.programme.programme_revision import ProgrammeRevision


class ProgrammeBaseline(Base):
    __tablename__ = "programme_baselines"

    __table_args__ = (
        UniqueConstraint(
            "programme_id",
            "name",
            name="uq_programme_baseline_name",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    programme_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("programmes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source_revision_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("programme_revisions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    baseline_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
        server_default="active",
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

    programme: Mapped[Programme] = relationship(
        back_populates="baselines",
    )

    source_revision: Mapped[ProgrammeRevision] = relationship(
        back_populates="baselines",
    )

    activities: Mapped[list[ProgrammeBaselineActivity]] = relationship(
        back_populates="baseline",
        cascade="all, delete-orphan",
    )
