import enum
import uuid

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Time, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MedicationForm(enum.StrEnum):
    """Physical form of the medication."""

    TABLET = "tablet"
    CAPSULE = "capsule"
    SYRUP = "syrup"
    CREAM = "cream"
    OINTMENT = "ointment"
    INHALER = "inhaler"
    INJECTION = "injection"
    DROPS = "drops"
    SPRAY = "spray"
    SUPPOSITORY = "suppository"
    PATCH = "patch"


class MedicationFrequency(enum.StrEnum):
    """How often the medication should be taken."""

    DAILY = "daily"
    EVERY_OTHER_DAY = "every_other_day"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    AS_NEEDED = "as_needed"
    CUSTOM = "custom"


class DosageUnit(enum.StrEnum):
    """Unit of measurement for dosage."""

    MG = "mg"
    ML = "ml"
    UNITS = "units"
    PUFFS = "puffs"
    DROPS = "drops"
    PIECES = "pieces"
    APPLICATIONS = "applications"


class ItemType(enum.StrEnum):
    """Type of trackable item."""

    MEDICATION = "medication"
    EXERCISE = "exercise"
    WATER_INTAKE = "water_intake"


class Medication(Base):
    """A medication registered by the user. Includes refill tracking."""

    __tablename__ = "medications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    item_type: Mapped[str] = mapped_column(
        String(20), default=ItemType.MEDICATION, nullable=False
    )
    medication_form: Mapped[str | None] = mapped_column(String(20), nullable=True)
    dosage: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # Legacy free-text field, kept for backward compatibility
    dosage_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    dosage_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    frequency: Mapped[str] = mapped_column(
        String(50), default=MedicationFrequency.DAILY, nullable=False
    )
    times_per_day: Mapped[int] = mapped_column(Integer, nullable=False)
    supply_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_refill_date: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    treatment_end_date: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    refill_reminder_days_before: Mapped[int] = mapped_column(Integer, default=3)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="medications")
    schedules: Mapped[list["MedicationSchedule"]] = relationship(
        back_populates="medication"
    )

    def __repr__(self) -> str:
        return (
            f"<Medication(id={self.id}, name={self.name}, form={self.medication_form})>"
        )


class MedicationSchedule(Base):
    """A specific time a medication should be taken. Celery Beat picks these up."""

    __tablename__ = "medication_schedules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    medication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("medications.id"),
        nullable=False,
        index=True,
    )
    scheduled_time: Mapped[Time] = mapped_column(Time, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    medication: Mapped["Medication"] = relationship(back_populates="schedules")
    reminder_logs: Mapped[list["ReminderLog"]] = relationship(back_populates="schedule")

    def __repr__(self) -> str:
        return f"<MedicationSchedule(id={self.id}, time={self.scheduled_time})>"


from app.models.reminder import ReminderLog  # noqa: E402
from app.models.user import User  # noqa: E402
