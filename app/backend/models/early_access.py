from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.backend.database.base import Base


class EarlyAccessApplication(Base):
    __tablename__ = "early_access_applications"

    __table_args__ = (
        UniqueConstraint(
            "work_email",
            name="uq_early_access_applications_work_email",
        ),
        CheckConstraint(
            "length(trim(full_name)) BETWEEN 1 AND 200",
            name="ck_early_access_full_name_length",
        ),
        CheckConstraint(
            "length(work_email) BETWEEN 3 AND 320 "
            "AND work_email = lower(trim(work_email))",
            name="ck_early_access_work_email_normalized",
        ),
        CheckConstraint(
            "length(trim(company_name)) BETWEEN 1 AND 200",
            name="ck_early_access_company_name_length",
        ),
        CheckConstraint(
            "length(trim(job_title)) BETWEEN 1 AND 160",
            name="ck_early_access_job_title_length",
        ),
        CheckConstraint(
            "length(trim(subcontractor_type)) BETWEEN 1 AND 160",
            name="ck_early_access_trade_length",
        ),
        CheckConstraint(
            "company_size IN ('1-10', '11-50', '51-150', '151-500', '500+')",
            name="ck_early_access_company_size",
        ),
        CheckConstraint(
            "active_projects IN ('1-3', '4-10', '11-25', '26-50', '50+')",
            name="ck_early_access_active_projects",
        ),
        CheckConstraint(
            "length(trim(current_tools)) BETWEEN 1 AND 2000",
            name="ck_early_access_current_tools_length",
        ),
        CheckConstraint(
            "length(trim(biggest_delivery_challenge)) BETWEEN 1 AND 4000",
            name="ck_early_access_challenge_length",
        ),
        CheckConstraint(
            "interest_level IN ('early_access', 'pilot_customer', 'design_partner')",
            name="ck_early_access_interest_level",
        ),
        CheckConstraint(
            "additional_information IS NULL "
            "OR length(additional_information) <= 4000",
            name="ck_early_access_additional_information_length",
        ),
        CheckConstraint(
            "length(ip_address_hash) = 64",
            name="ck_early_access_ip_hash_length",
        ),
        CheckConstraint(
            "user_agent IS NULL OR length(user_agent) <= 500",
            name="ck_early_access_user_agent_length",
        ),
        Index("ix_early_access_applications_created_at", "created_at"),
        Index(
            "ix_early_access_applications_ip_address_hash",
            "ip_address_hash",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    work_email: Mapped[str] = mapped_column(String(320), nullable=False)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    job_title: Mapped[str] = mapped_column(String(160), nullable=False)
    subcontractor_type: Mapped[str] = mapped_column(String(160), nullable=False)
    company_size: Mapped[str] = mapped_column(String(80), nullable=False)
    active_projects: Mapped[str] = mapped_column(String(80), nullable=False)
    current_tools: Mapped[str] = mapped_column(Text, nullable=False)
    biggest_delivery_challenge: Mapped[str] = mapped_column(Text, nullable=False)
    interest_level: Mapped[str] = mapped_column(String(40), nullable=False)
    additional_information: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    ip_address_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
