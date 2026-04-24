import uuid

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ReminderLog(Base):
    """A log entry for a single reminder event.

    Status lifecycle: pending → sent → taken / missed / snoozed
    """

    __tablename__ = "reminder_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("medication_schedules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending, sent, taken, missed, snoozed
    scheduled_for: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    sent_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    marked_missed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    schedule: Mapped["MedicationSchedule"] = relationship(
        back_populates="reminder_logs"
    )
    user: Mapped["User"] = relationship(back_populates="reminder_logs")

    def __repr__(self) -> str:
        return f"<ReminderLog(id={self.id}, status={self.status})>"


from app.models.medication import MedicationSchedule  # noqa: E402
from app.models.user import User  # noqa: E402
