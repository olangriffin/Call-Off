from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.backend.database.base import Base

if TYPE_CHECKING:
    from app.backend.models.programme.programme import Programme
    from app.backend.models.programme.programme_activity import ProgrammeActivity


class ProgrammeActivityIdentity(Base):
    """Stable logical identity for an activity across Programme revisions."""

    __tablename__ = "programme_activity_identities"

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

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    programme: Mapped[Programme] = relationship(
        back_populates="activity_identities",
    )

    activities: Mapped[list[ProgrammeActivity]] = relationship(
        back_populates="activity_identity",
        passive_deletes=True,
    )
