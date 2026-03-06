from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.subscription import SubscriptionCreate
from app.schemas.user import UserCreate, UserProfileCreate
from app.services.subscription_service import subscription_service
from app.services.user_service import user_service


@pytest.fixture
async def test_user_for_sub(db: AsyncSession):
    user_in = UserCreate(
        profile=UserProfileCreate(
            whatsapp_number="+2348123456780", first_name="Sub", last_name="Tester"
        )
    )
    return await user_service.create(db, user_in=user_in)


@pytest.mark.asyncio
async def test_create_subscription(db: AsyncSession, test_user_for_sub):
    """Test creating a subscription for a user."""
    sub_in = SubscriptionCreate(
        plan="monthly",
        status="active",
        amount_kobo=50000,
        starts_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=30),
        auto_renew=True,
    )

    sub = await subscription_service.create_subscription(
        db, user_id=test_user_for_sub.id, obj_in=sub_in
    )

    assert sub is not None
    assert sub.status == "active"
    assert sub.user_id == test_user_for_sub.id


@pytest.mark.asyncio
async def test_get_user_subscription(db: AsyncSession, test_user_for_sub):
    """Test fetching a user's active subscription."""
    sub_in = SubscriptionCreate(plan="monthly", status="active", amount_kobo=50000)
    await subscription_service.create_subscription(
        db, user_id=test_user_for_sub.id, obj_in=sub_in
    )

    sub = await subscription_service.get_user_subscription(
        db, user_id=test_user_for_sub.id
    )
    assert sub is not None
    assert sub.status == "active"
