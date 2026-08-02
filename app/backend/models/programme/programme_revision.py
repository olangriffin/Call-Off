from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.backend.database.base import Base

if TYPE_CHECKING:
    from app.backend.models.programme.programme import Programme
    from app.backend.models.programme.programme_activity import ProgrammeActivity
    from app.backend.models.programme.programme_baseline import ProgrammeBaseline
    from app.backend.models.programme.programme_import import ProgrammeImport


class ProgrammeRevision(Base):
    __tablename__ = "programme_revisions"

    __table_args__ = (
        UniqueConstraint(
            "programme_id",
            "revision_code",
            name="uq_programme_revisions_code",
        ),
        Index(
            "uq_programme_revisions_current",
            "programme_id",
            unique=True,
            postgresql_where=text("is_current = true"),
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
    activities: Mapped[list[ProgrammeActivity]] = relationship(
        back_populates="programme_revision",
        cascade="all, delete-orphan",
    )

    revision_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="manual",
        server_default="manual",
    )

    source_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="draft",
        server_default="draft",
    )

    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )

    revision_date: Mapped[date | None] = mapped_column(
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

    programme: Mapped[Programme] = relationship(
        back_populates="revisions",
    )

    baselines: Mapped[list[ProgrammeBaseline]] = relationship(
        back_populates="source_revision",
    )

    imports: Mapped[list[ProgrammeImport]] = relationship(
        back_populates="programme_revision",
    )
