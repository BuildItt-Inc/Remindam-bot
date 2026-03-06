"""fix message_logs columns

Revision ID: 903bbe38c426
Revises: 6d64bc3bf910
Create Date: 2026-03-06 12:17:13.407270

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "903bbe38c426"
down_revision: str | Sequence[str] | None = "6d64bc3bf910"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "message_logs", sa.Column("reminder_log_id", sa.UUID(), nullable=True)
    )
    op.create_foreign_key(
        "fk_message_logs_reminder_log_id",
        "message_logs",
        "reminder_logs",
        ["reminder_log_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_message_logs_reminder_log_id"),
        "message_logs",
        ["reminder_log_id"],
        unique=False,
    )

    op.drop_column("message_logs", "content")
    op.drop_column("message_logs", "message_type")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "message_logs",
        sa.Column(
            "message_type", sa.VARCHAR(length=20), autoincrement=False, nullable=True
        ),
    )
    op.add_column(
        "message_logs",
        sa.Column("content", sa.TEXT(), autoincrement=False, nullable=True),
    )
    op.drop_index(op.f("ix_message_logs_reminder_log_id"), table_name="message_logs")
    op.drop_constraint(
        "fk_message_logs_reminder_log_id", "message_logs", type_="foreignkey"
    )
    op.drop_column("message_logs", "reminder_log_id")
