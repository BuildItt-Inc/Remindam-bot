from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AdherenceReportBase(BaseModel):
    report_type: str  # "weekly" or "monthly"
    period_start: datetime
    period_end: datetime


class AdherenceReportCreate(AdherenceReportBase):
    user_id: UUID
    total_reminders: int = 0
    taken_count: int = 0
    missed_count: int = 0
    adherence_percentage: float = 0.0


class AdherenceReportResponse(AdherenceReportBase):
    id: UUID
    user_id: UUID
    total_reminders: int
    taken_count: int
    missed_count: int
    adherence_percentage: float
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)
