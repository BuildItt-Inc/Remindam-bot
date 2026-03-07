import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """Non-sensitive user record. PII is isolated in UserProfile for NDPR compliance."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    trial_start_date: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    profile: Mapped["UserProfile"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="user")
    payments: Mapped[list["Payment"]] = relationship(back_populates="user")
    medications: Mapped[list["Medication"]] = relationship(back_populates="user")
    reminder_logs: Mapped[list["ReminderLog"]] = relationship(back_populates="user")
    message_logs: Mapped[list["MessageLog"]] = relationship(back_populates="user")
    adherence_reports: Mapped[list["AdherenceReport"]] = relationship(
        back_populates="user"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, is_active={self.is_active})>"


class UserProfile(Base):
    """Sensitive PII + user settings. 1:1 with User. Isolated for NDPR compliance."""

    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    whatsapp_number: Mapped[str] = mapped_column(
        Text, unique=True, nullable=False, index=True
    )
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    reminder_window_minutes: Mapped[int] = mapped_column(Integer, default=30)
    notification_preferences: Mapped[str] = mapped_column(
        String(20), default="whatsapp"
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="profile")

    def __repr__(self) -> str:
        return f"<UserProfile(user_id={self.user_id}, whatsapp={self.whatsapp_number})>"


from app.models.adherence_report import AdherenceReport  # noqa: E402
from app.models.medication import Medication  # noqa: E402
from app.models.message import MessageLog  # noqa: E402
from app.models.payment import Payment  # noqa: E402
from app.models.reminder import ReminderLog  # noqa: E402
from app.models.subscription import Subscription  # noqa: E402
