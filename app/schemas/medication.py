from datetime import datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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
    name: str
    dosage: str | None = None
    times_per_day: int
    supply_days: int | None = None
    next_refill_date: datetime | None = None
    refill_reminder_days_before: int = 3


class MedicationCreate(MedicationBase):
    schedules: list[MedicationScheduleCreate]


class MedicationUpdate(BaseModel):
    name: str | None = None
    dosage: str | None = None
    times_per_day: int | None = None
    supply_days: int | None = None
    next_refill_date: datetime | None = None
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
