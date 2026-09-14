"""drop obsolete better-auth public tables

Revision ID: d9aae884c197
Revises: d8b88096af86
Create Date: 2026-07-26 21:39:37.228282

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "d9aae884c197"
down_revision: str | Sequence[str] | None = "d8b88096af86"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Leave the externally managed Alembic table unchanged."""


def downgrade() -> None:
    """No-op because this revision no longer changes external state."""
