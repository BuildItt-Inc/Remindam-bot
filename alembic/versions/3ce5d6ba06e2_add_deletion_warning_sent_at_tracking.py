"""add deletion warning sent at tracking

Revision ID: 3ce5d6ba06e2
Revises: 269f1c512db4
Create Date: 2026-04-24 21:21:33.256127

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3ce5d6ba06e2"
down_revision: str | Sequence[str] | None = "269f1c512db4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column(
            "deletion_warning_sent_at", sa.DateTime(timezone=True), nullable=True
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "deletion_warning_sent_at")
