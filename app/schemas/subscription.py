from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SubscriptionBase(BaseModel):
    plan: str
    status: str
    amount_kobo: int | None = None
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    auto_renew: bool = True
    trial_ends_at: datetime | None = None


class SubscriptionCreate(SubscriptionBase):
    pass


class SubscriptionUpdate(BaseModel):
    plan: str | None = None
    status: str | None = None
    amount_kobo: int | None = None
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    auto_renew: bool | None = None
    trial_ends_at: datetime | None = None


class SubscriptionResponse(SubscriptionBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
