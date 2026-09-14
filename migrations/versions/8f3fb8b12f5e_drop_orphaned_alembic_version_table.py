"""drop orphaned alembic_version table

Revision ID: 8f3fb8b12f5e
Revises: d9aae884c197
Create Date: 2026-07-26 21:41:59.097652

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "8f3fb8b12f5e"
down_revision: str | Sequence[str] | None = "d9aae884c197"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Leave the externally managed Alembic table unchanged."""


def downgrade() -> None:
    """No-op because this revision no longer changes external state."""
