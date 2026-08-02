from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.backend.database.base import Base

if TYPE_CHECKING:
    from app.backend.models.programme.programme import Programme
    from app.backend.models.programme.programme_revision import ProgrammeRevision


class ProgrammeImport(Base):
    __tablename__ = "programme_imports"

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

    programme_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("programme_revisions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    source_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    source_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    checksum: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    total_records: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    imported_records: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    warning_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    error_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    mapping_config: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    validation_issues: Mapped[list[dict] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    programme: Mapped[Programme] = relationship(
        back_populates="imports",
    )

    programme_revision: Mapped[ProgrammeRevision | None] = relationship(
        back_populates="imports",
    )
