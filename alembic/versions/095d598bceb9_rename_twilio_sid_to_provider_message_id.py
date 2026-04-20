"""rename twilio_sid to provider_message_id

Revision ID: 095d598bceb9
Revises: fb7303f5f48e
Create Date: 2026-03-14 12:14:07.929023

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "095d598bceb9"
down_revision: str | Sequence[str] | None = "fb7303f5f48e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("message_logs", "twilio_sid", new_column_name="provider_message_id")
    op.drop_index(op.f("ix_message_logs_twilio_sid"), table_name="message_logs")
    op.create_index(
        op.f("ix_message_logs_provider_message_id"),
        "message_logs",
        ["provider_message_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("message_logs", "provider_message_id", new_column_name="twilio_sid")
    op.drop_index(
        op.f("ix_message_logs_provider_message_id"), table_name="message_logs"
    )
    op.create_index(
        op.f("ix_message_logs_twilio_sid"), "message_logs", ["twilio_sid"], unique=False
    )
