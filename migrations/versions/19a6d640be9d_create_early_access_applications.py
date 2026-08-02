"""create early access applications table

Revision ID: 19a6d640be9d
Revises: fef0ab6525da
Create Date: 2026-08-01 01:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "19a6d640be9d"
down_revision: str | Sequence[str] | None = "fef0ab6525da"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "early_access_applications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("work_email", sa.String(length=320), nullable=False),
        sa.Column("company_name", sa.String(length=200), nullable=False),
        sa.Column("job_title", sa.String(length=160), nullable=False),
        sa.Column("subcontractor_type", sa.String(length=160), nullable=False),
        sa.Column("company_size", sa.String(length=80), nullable=False),
        sa.Column("active_projects", sa.String(length=80), nullable=False),
        sa.Column("current_tools", sa.Text(), nullable=False),
        sa.Column("biggest_delivery_challenge", sa.Text(), nullable=False),
        sa.Column("interest_level", sa.String(length=40), nullable=False),
        sa.Column("additional_information", sa.Text(), nullable=True),
        sa.Column("ip_address_hash", sa.String(length=64), nullable=False),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "work_email",
            name="uq_early_access_applications_work_email",
        ),
    )
    op.create_index(
        op.f("ix_early_access_applications_created_at"),
        "early_access_applications",
        ["created_at"],
    )
    op.create_index(
        op.f("ix_early_access_applications_ip_address_hash"),
        "early_access_applications",
        ["ip_address_hash"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_early_access_applications_ip_address_hash"),
        table_name="early_access_applications",
    )
    op.drop_index(
        op.f("ix_early_access_applications_created_at"),
        table_name="early_access_applications",
    )
    op.drop_table("early_access_applications")
