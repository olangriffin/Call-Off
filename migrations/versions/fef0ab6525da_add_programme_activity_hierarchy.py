"""add programme activity hierarchy

Revision ID: fef0ab6525da
Revises: 7d7edb21bfc9
Create Date: 2026-07-26 22:44:39.525642

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fef0ab6525da"
down_revision: str | Sequence[str] | None = "7d7edb21bfc9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "programme_activities",
        sa.Column("parent_activity_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "programme_activities",
        sa.Column(
            "is_summary",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_programme_activities_parent_id",
        "programme_activities",
        "programme_activities",
        ["parent_activity_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        op.f("ix_programme_activities_parent_activity_id"),
        "programme_activities",
        ["parent_activity_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_programme_activities_parent_activity_id"),
        table_name="programme_activities",
    )
    op.drop_constraint(
        "fk_programme_activities_parent_id",
        "programme_activities",
        type_="foreignkey",
    )
    op.drop_column("programme_activities", "is_summary")
    op.drop_column("programme_activities", "parent_activity_id")
