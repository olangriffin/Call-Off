"""actually drop orphaned alembic_version table

Revision ID: 7d7edb21bfc9
Revises: 8f3fb8b12f5e
Create Date: 2026-07-26 21:46:09.355313

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7d7edb21bfc9"
down_revision: str | Sequence[str] | None = "8f3fb8b12f5e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table("alembic_version")


def downgrade() -> None:
    """Downgrade schema."""
    raise NotImplementedError(
        "This migration drops an orphaned, unused legacy tracking table. "
        "No data was lost — Call-Off's migrations are tracked via "
        "calloff_alembic_version, not this table."
    )
