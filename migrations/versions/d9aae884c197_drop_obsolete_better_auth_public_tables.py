"""drop obsolete better-auth public tables

Revision ID: d9aae884c197
Revises: d8b88096af86
Create Date: 2026-07-26 21:39:37.228282

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9aae884c197"
down_revision: str | Sequence[str] | None = "d8b88096af86"
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
