from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.backend.database.base import Base


class AuthSession(Base):
    __tablename__ = "session"
    __table_args__ = {"schema": "neon_auth"}

    id: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
    )

    expires_at: Mapped[datetime] = mapped_column(
        "expiresAt",
        DateTime(timezone=False),
        nullable=False,
    )

    token: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        "createdAt",
        DateTime(timezone=False),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        "updatedAt",
        DateTime(timezone=False),
        nullable=False,
    )

    ip_address: Mapped[str | None] = mapped_column(
        "ipAddress",
        Text,
        nullable=True,
    )

    user_agent: Mapped[str | None] = mapped_column(
        "userAgent",
        Text,
        nullable=True,
    )

    user_id: Mapped[str] = mapped_column(
        "userId",
        Text,
        ForeignKey(
            "neon_auth.user.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    active_organization_id: Mapped[str | None] = mapped_column(
        "activeOrganizationId",
        Text,
        nullable=True,
    )
