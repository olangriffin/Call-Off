from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
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


class Membership(Base):
    __tablename__ = "memberships"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            name="uq_memberships_one_org_per_user",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("neon_auth.user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    organization_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="member",
        server_default="member",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
        server_default="active",
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    revoked_by: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("neon_auth.user.id"),
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
        back_populates="memberships",
    )
