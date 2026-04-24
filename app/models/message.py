import uuid

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MessageLog(Base):
    """Lite log of a WhatsApp message for delivery tracking.
    Sensitive content is NOT stored for privacy compliance.
    """

    __tablename__ = "message_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    reminder_log_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reminder_logs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    direction: Mapped[str] = mapped_column(
        String(10), nullable=False, default="outbound"
    )  # inbound, outbound
    provider_message_id: Mapped[str | None] = mapped_column(String(50), index=True)
    status: Mapped[str | None] = mapped_column(
        String(20)
    )  # queued, sent, delivered, failed
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped["User | None"] = relationship(back_populates="message_logs")
    reminder_log: Mapped["ReminderLog | None"] = relationship()


from app.models.reminder import ReminderLog  # noqa: E402
from app.models.user import User  # noqa: E402
