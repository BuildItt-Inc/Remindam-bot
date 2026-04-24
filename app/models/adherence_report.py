import uuid

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AdherenceReport(Base):
    """Weekly or monthly consistency report for a user (paid feature).

    Tracks how well the user adhered to their medication schedule
    over a given period.
    """

    __tablename__ = "adherence_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_type: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # "weekly" or "monthly"
    period_start: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    period_end: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    total_reminders: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    taken_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    adherence_percentage: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    generated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="adherence_reports")

    def __repr__(self) -> str:
        return (
            f"<AdherenceReport(id={self.id}, type={self.report_type}, "
            f"adherence={self.adherence_percentage:.1f}%)>"
        )


from app.models.user import User  # noqa: E402
