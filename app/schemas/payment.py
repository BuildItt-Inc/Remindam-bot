from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PaymentBase(BaseModel):
    amount: int
    currency: str = "NGN"
    status: str
    reference: str
    provider: str | None = None


class PaymentCreate(PaymentBase):
    subscription_id: UUID | None = None


class PaymentUpdate(BaseModel):
    status: str | None = None
    completed_at: datetime | None = None


class PaymentResponse(PaymentBase):
    id: UUID
    user_id: UUID
    subscription_id: UUID | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
