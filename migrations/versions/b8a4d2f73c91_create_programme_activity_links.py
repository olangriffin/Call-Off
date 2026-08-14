"""create programme activity links

Revision ID: b8a4d2f73c91
Revises: 72b5c9e1083f
Create Date: 2026-08-14 23:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8a4d2f73c91"
down_revision: str | Sequence[str] | None = "72b5c9e1083f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create client-to-internal programme activity links."""
    op.create_table(
        "programme_activity_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_activity_id", sa.Uuid(), nullable=False),
        sa.Column("target_activity_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_activity_id <> target_activity_id",
            name="ck_programme_activity_link_not_self",
        ),
        sa.ForeignKeyConstraint(
            ["source_activity_id"],
            ["programme_activities.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_activity_id"],
            ["programme_activities.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_activity_id",
            "target_activity_id",
            name="uq_programme_activity_link",
        ),
    )
    op.create_index(
        op.f("ix_programme_activity_links_source_activity_id"),
        "programme_activity_links",
        ["source_activity_id"],
    )
    op.create_index(
        op.f("ix_programme_activity_links_target_activity_id"),
        "programme_activity_links",
        ["target_activity_id"],
    )


def downgrade() -> None:
    """Drop programme activity links."""
    op.drop_index(
        op.f("ix_programme_activity_links_target_activity_id"),
        table_name="programme_activity_links",
    )
    op.drop_index(
        op.f("ix_programme_activity_links_source_activity_id"),
        table_name="programme_activity_links",
    )
    op.drop_table("programme_activity_links")
