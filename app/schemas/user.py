from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserProfileBase(BaseModel):
    whatsapp_number: str
    first_name: str | None = None
    last_name: str | None = None
    timezone: str = "UTC"
    reminder_window_minutes: int = 30
    notification_preferences: str = "whatsapp"


class UserProfileCreate(UserProfileBase):
    pass


class UserProfileUpdate(BaseModel):
    whatsapp_number: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    timezone: str | None = None
    reminder_window_minutes: int | None = None
    notification_preferences: str | None = None


class UserProfileResponse(UserProfileBase):
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    profile: UserProfileCreate


class UserUpdate(BaseModel):
    is_active: bool | None = None
    profile: UserProfileUpdate | None = None


class UserResponse(BaseModel):
    id: UUID
    is_active: bool
    trial_start_date: datetime
    created_at: datetime
    updated_at: datetime
    profile: UserProfileResponse | None = None

    model_config = ConfigDict(from_attributes=True)
