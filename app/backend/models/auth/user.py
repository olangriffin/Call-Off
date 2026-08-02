from datetime import datetime

from sqlalchemy import Boolean, DateTime, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.backend.database.base import Base


class AuthUser(Base):
    __tablename__ = "user"
    __table_args__ = {"schema": "neon_auth"}

    id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
    )

    email_verified: Mapped[bool] = mapped_column(
        "emailVerified",
        Boolean,
        nullable=False,
    )

    image: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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
