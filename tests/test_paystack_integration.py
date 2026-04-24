from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment
from app.models.subscription import Subscription
from app.payment import process_successful_payment
from app.schemas.user import UserCreate, UserProfileCreate
from app.services.flow_service import flow_service
from app.services.user_service import user_service


@pytest.fixture
async def pay_user(db: AsyncSession):
    user_in = UserCreate(
        profile=UserProfileCreate(
            whatsapp_number="+2347000000002", first_name="Pay", last_name="Tester"
        )
    )
    return await user_service.create(db, user_in=user_in)


@pytest.mark.asyncio
async def test_dynamic_upgrade_flow_simulation(db: AsyncSession, pay_user):
    """
    Test that tapping upgrade generates a unique Paystack link
    and creates a DB record.
    """

    mock_response = {
        "status": True,
        "message": "Authorization URL created",
        "data": {
            "authorization_url": "https://checkout.paystack.com/test-link",
            "access_code": "test_code",
            "reference": "rem_test123",
        },
    }

    with (
        patch("httpx.AsyncClient.post") as mock_post,
        patch("app.services.payment_service.settings.PAYSTACK_SECRET_KEY", "test_key"),
    ):
        mock_post.return_value = AsyncMock(
            status_code=200, json=lambda: mock_response, raise_for_status=lambda: None
        )

        msg, next_state, state_data = await flow_service.handle(
            db, pay_user, "idle", {}, "menu_upgrade"
        )

        assert "https://checkout.paystack.com/test-link" in msg.body

        query = select(Payment).where(Payment.user_id == pay_user.id)
        result = await db.execute(query)
        payment = result.scalars().first()

        assert payment is not None
        assert payment.status == "pending"
        assert payment.reference.startswith("rem_")


@pytest.mark.asyncio
async def test_webhook_activation_simulation(db: AsyncSession, pay_user):
    """Test that a successful webhook activates the subscription."""

    from app.models.payment import Payment

    sub = Subscription(
        user_id=pay_user.id, plan="monthly", status="pending", amount_kobo=50000
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)

    ref = "rem_webhook_test"
    payment = Payment(
        user_id=pay_user.id,
        subscription_id=sub.id,
        amount=50000,
        currency="NGN",
        status="pending",
        reference=ref,
        provider="paystack",
    )
    db.add(payment)
    await db.commit()

    success = await process_successful_payment(db, ref)
    assert success is True

    await db.refresh(payment)
    assert payment.status == "successful"

    await db.refresh(sub)
    assert sub.status == "active"
    assert sub.starts_at is not None
    assert sub.expires_at is not None
