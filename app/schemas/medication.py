from datetime import datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.medication import (
    DosageUnit,
    ItemType,
    MedicationFrequency,
)


class MedicationScheduleBase(BaseModel):
    scheduled_time: time


class MedicationScheduleCreate(MedicationScheduleBase):
    pass


class MedicationScheduleUpdate(BaseModel):
    scheduled_time: time | None = None
    is_active: bool | None = None


class MedicationScheduleResponse(MedicationScheduleBase):
    id: UUID
    medication_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MedicationBase(BaseModel):
    name: str = Field(..., max_length=150)
    item_type: ItemType = ItemType.MEDICATION
    medication_form: str | None = None
    dosage: str | None = Field(None, max_length=150)
    dosage_amount: float | None = None
    dosage_unit: DosageUnit | None = None
    frequency: MedicationFrequency = MedicationFrequency.DAILY
    times_per_day: int = 1
    supply_days: int | None = None
    next_refill_date: datetime | None = None
    treatment_end_date: datetime | None = None
    refill_reminder_days_before: int = 3


class MedicationCreate(MedicationBase):
    schedules: list[MedicationScheduleCreate]


class MedicationUpdate(BaseModel):
    name: str | None = None
    item_type: ItemType | None = None
    medication_form: str | None = None
    dosage: str | None = None
    dosage_amount: float | None = None
    dosage_unit: DosageUnit | None = None
    frequency: MedicationFrequency | None = None
    times_per_day: int | None = None
    supply_days: int | None = None
    next_refill_date: datetime | None = None
    treatment_end_date: datetime | None = None
    refill_reminder_days_before: int | None = None
    is_active: bool | None = None


class MedicationResponse(MedicationBase):
    id: UUID
    user_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    schedules: list[MedicationScheduleResponse] = []

    model_config = ConfigDict(from_attributes=True)
