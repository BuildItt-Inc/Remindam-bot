from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ReminderLogBase(BaseModel):
    status: str = "pending"
    scheduled_for: datetime


class ReminderLogCreate(ReminderLogBase):
    schedule_id: UUID
    user_id: UUID


class ReminderLogUpdate(BaseModel):
    status: str | None = None
    sent_at: datetime | None = None
    responded_at: datetime | None = None
    marked_missed_at: datetime | None = None


class ReminderLogResponse(ReminderLogBase):
    id: UUID
    schedule_id: UUID
    user_id: UUID
    sent_at: datetime | None = None
    responded_at: datetime | None = None
    marked_missed_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
