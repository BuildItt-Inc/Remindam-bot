"""
MessageLog model.

Raw audit log of every WhatsApp message (in/out) via Twilio.
Essential for debugging delivery issues.
"""

import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MessageLog(Base):
    """A log of a single WhatsApp message sent or received via Twilio."""

    __tablename__ = "message_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    direction: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # inbound, outbound
    message_type: Mapped[str | None] = mapped_column(
        String(20)
    )  # reminder, reply, onboarding, payment
    content: Mapped[str | None] = mapped_column(Text)
    twilio_sid: Mapped[str | None] = mapped_column(String(50), index=True)
    status: Mapped[str | None] = mapped_column(
        String(20)
    )  # queued, sent, delivered, failed
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped["User | None"] = relationship(back_populates="message_logs")

    def __repr__(self) -> str:
        return f"<MessageLog(id={self.id}, direction={self.direction})>"


from app.models.user import User  # noqa: E402
