"""add programme type

Revision ID: 72b5c9e1083f
Revises: c4e21d8a3f70
Create Date: 2026-08-14 22:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "72b5c9e1083f"
down_revision: str | Sequence[str] | None = "c4e21d8a3f70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add typed client and internal programmes per project."""
    op.add_column(
        "programmes",
        sa.Column(
            "programme_type",
            sa.String(length=20),
            server_default="internal",
            nullable=False,
        ),
    )
    op.execute(
        sa.text(
            "UPDATE programmes "
            "SET programme_type = 'internal' "
            "WHERE programme_type IS DISTINCT FROM 'internal'"
        )
    )
    op.create_check_constraint(
        "ck_programmes_type",
        "programmes",
        "programme_type IN ('client', 'internal')",
    )
    op.drop_index("ix_programmes_project_id", table_name="programmes")
    op.create_index(
        "ix_programmes_project_id",
        "programmes",
        ["project_id"],
    )
    op.create_unique_constraint(
        "uq_programmes_project_type",
        "programmes",
        ["project_id", "programme_type"],
    )


def downgrade() -> None:
    """Restore one untyped programme per project."""
    op.drop_constraint(
        "uq_programmes_project_type",
        "programmes",
        type_="unique",
    )
    # The previous schema can retain only one programme per project. Preserve
    # the internal workspace and remove its client counterpart before restoring
    # the old unique project index.
    op.execute(
        sa.text(
            "DELETE FROM programmes AS client_programme "
            "USING programmes AS internal_programme "
            "WHERE client_programme.project_id = internal_programme.project_id "
            "AND client_programme.programme_type = 'client' "
            "AND internal_programme.programme_type = 'internal'"
        )
    )
    op.drop_index("ix_programmes_project_id", table_name="programmes")
    op.create_index(
        "ix_programmes_project_id",
        "programmes",
        ["project_id"],
        unique=True,
    )
    op.drop_constraint(
        "ck_programmes_type",
        "programmes",
        type_="check",
    )
    op.drop_column("programmes", "programme_type")
