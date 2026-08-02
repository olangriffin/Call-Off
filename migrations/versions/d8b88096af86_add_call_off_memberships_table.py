"""add call-off memberships table

Revision ID: d8b88096af86
Revises: 916e9c81163d
Create Date: 2026-07-26 21:19:39.612231

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d8b88096af86"
down_revision: str | Sequence[str] | None = "916e9c81163d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column(
            "role", sa.String(length=30), server_default="member", nullable=False
        ),
        sa.Column(
            "status", sa.String(length=20), server_default="active", nullable=False
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["neon_auth.user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["revoked_by"], ["neon_auth.user.id"]),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_memberships_one_org_per_user"),
    )
    op.create_index(
        op.f("ix_memberships_user_id"), "memberships", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_memberships_organization_id"),
        "memberships",
        ["organization_id"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO memberships (id, user_id, organization_id, role, status)
        VALUES (
            gen_random_uuid(),
            '9d530e5b-9bae-4337-8e8a-a04b2203a0bb',
            'KBYBmC68tnIxyYhC0x4ckE3iRRm9Vm8q',
            'owner',
            'active'
        )
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_memberships_organization_id"), table_name="memberships")
    op.drop_index(op.f("ix_memberships_user_id"), table_name="memberships")
    op.drop_table("memberships")
