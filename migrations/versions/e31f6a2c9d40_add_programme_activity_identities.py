"""add stable programme activity identities

Revision ID: e31f6a2c9d40
Revises: c4e21d8a3f70
Create Date: 2026-09-16 09:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e31f6a2c9d40"
down_revision: str | Sequence[str] | None = "c4e21d8a3f70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Introduce durable activity identities across Programme revisions."""

    op.create_table(
        "programme_activity_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("programme_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["programme_id"],
            ["programmes.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_programme_activity_identities_programme_id",
        "programme_activity_identities",
        ["programme_id"],
        unique=False,
    )

    op.add_column(
        "programme_activities",
        sa.Column("activity_identity_id", sa.Uuid(), nullable=True),
    )

    # Existing revision rows pre-date durable identity. Give each existing row
    # its own identity so the migration is lossless; all new revision creation
    # paths can then deliberately reuse an identity when continuity is known.
    op.execute(
        "UPDATE programme_activities "
        "SET activity_identity_id = gen_random_uuid() "
        "WHERE activity_identity_id IS NULL"
    )
    op.execute(
        "INSERT INTO programme_activity_identities (id, programme_id) "
        "SELECT pa.activity_identity_id, pr.programme_id "
        "FROM programme_activities AS pa "
        "JOIN programme_revisions AS pr ON pr.id = pa.programme_revision_id "
        "ON CONFLICT (id) DO NOTHING"
    )

    op.alter_column(
        "programme_activities",
        "activity_identity_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.create_foreign_key(
        "fk_programme_activities_identity_id",
        "programme_activities",
        "programme_activity_identities",
        ["activity_identity_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_programme_activities_activity_identity_id",
        "programme_activities",
        ["activity_identity_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_programme_activity_revision_identity",
        "programme_activities",
        ["programme_revision_id", "activity_identity_id"],
    )


def downgrade() -> None:
    """Remove durable activity identities."""

    op.drop_constraint(
        "uq_programme_activity_revision_identity",
        "programme_activities",
        type_="unique",
    )
    op.drop_index(
        "ix_programme_activities_activity_identity_id",
        table_name="programme_activities",
    )
    op.drop_constraint(
        "fk_programme_activities_identity_id",
        "programme_activities",
        type_="foreignkey",
    )
    op.drop_column("programme_activities", "activity_identity_id")
    op.drop_index(
        "ix_programme_activity_identities_programme_id",
        table_name="programme_activity_identities",
    )
    op.drop_table("programme_activity_identities")
