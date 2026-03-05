"""
Payment model.

Individual payment transactions (Paystack/Flutterwave charges).
"""

import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Payment(Base):
    """Individual payment transaction. Each row is one charge attempt."""

    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # Amount in kobo
    currency: Mapped[str] = mapped_column(String(3), default="NGN")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # pending, successful, failed
    reference: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    provider: Mapped[str | None] = mapped_column(String(20))  # flutterwave, paystack
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    user: Mapped["User"] = relationship(back_populates="payments")
    subscription: Mapped["Subscription | None"] = relationship(
        back_populates="payments"
    )

    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, status={self.status}, ref={self.reference})>"


from app.models.subscription import Subscription  # noqa: E402
from app.models.user import User  # noqa: E402
