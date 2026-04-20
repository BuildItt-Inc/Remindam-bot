import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.user import (
    UserCreate,
    UserProfileCreate,
    UserProfileUpdate,
    UserUpdate,
)
from app.services.user_service import user_service


@pytest.fixture
def sample_user_create() -> UserCreate:
    return UserCreate(
        profile=UserProfileCreate(
            whatsapp_number="+2348000000000",
            first_name="Test",
            last_name="User",
            timezone="Africa/Lagos",
        )
    )


@pytest.mark.asyncio
async def test_create_user(db: AsyncSession, sample_user_create: UserCreate):
    """Test creating a user and their profile via the user_service."""
    user = await user_service.create(db, user_in=sample_user_create)

    assert user is not None
    assert user.id is not None
    assert user.is_active is True
    assert user.profile is not None
    assert user.profile.whatsapp_number == "+2348000000000"
    assert user.profile.first_name == "Test"


@pytest.mark.asyncio
async def test_get_user_by_id(db: AsyncSession, sample_user_create: UserCreate):
    """Test retrieving a user by ID."""
    created_user = await user_service.create(db, user_in=sample_user_create)

    fetched_user = await user_service.get_by_id(db, created_user.id)
    assert fetched_user is not None
    assert fetched_user.id == created_user.id
    assert fetched_user.profile.whatsapp_number == created_user.profile.whatsapp_number


@pytest.mark.asyncio
async def test_get_user_by_whatsapp_number(
    db: AsyncSession, sample_user_create: UserCreate
):
    """Test retrieving a user by their WhatsApp number."""
    created_user = await user_service.create(db, user_in=sample_user_create)

    fetched_user = await user_service.get_by_whatsapp_number(
        db, sample_user_create.profile.whatsapp_number
    )
    assert fetched_user is not None
    assert fetched_user.id == created_user.id


@pytest.mark.asyncio
async def test_update_user(db: AsyncSession, sample_user_create: UserCreate):
    """Test updating user and user profile properties."""
    created_user = await user_service.create(db, user_in=sample_user_create)

    update_data = UserUpdate(
        is_active=False, profile=UserProfileUpdate(first_name="UpdatedName")
    )

    updated_user = await user_service.update(
        db, db_obj=created_user, obj_in=update_data
    )

    assert updated_user.is_active is False
    assert updated_user.profile.first_name == "UpdatedName"
    assert updated_user.profile.whatsapp_number == "+2348000000000"  # untouched
