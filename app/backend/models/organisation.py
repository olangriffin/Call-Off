from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.backend.database.base import Base

if TYPE_CHECKING:
    from app.backend.models.membership import Membership

    from app.backend.models.project import Project


class Organisation(Base):
    __tablename__ = "organization"

    id: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
    )

    logo: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        "createdAt",
        DateTime(timezone=True),
        nullable=False,
    )

    metadata_json: Mapped[str | None] = mapped_column(
        "metadata",
        Text,
        nullable=True,
    )

    projects: Mapped[list[Project]] = relationship(
        back_populates="organisation",
        cascade="all, delete-orphan",
    )

    memberships: Mapped[list[Membership]] = relationship(
        back_populates="organisation",
        cascade="all, delete-orphan",
    )
