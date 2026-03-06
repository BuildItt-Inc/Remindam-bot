from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MessageLogCreate(BaseModel):
    user_id: UUID
    reminder_log_id: UUID | None = None
    twilio_sid: str | None = None
    status: str = "sent"  # sent, delivered, failed
    direction: str = "outbound"


class MessageLogResponse(MessageLogCreate):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
