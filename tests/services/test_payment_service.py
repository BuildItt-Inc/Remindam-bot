from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.payment import PaymentCreate, PaymentUpdate
from app.schemas.user import UserCreate, UserProfileCreate
from app.services.payment_service import payment_service
from app.services.user_service import user_service


@pytest.fixture
async def test_user_for_payment(db: AsyncSession):
    user_in = UserCreate(
        profile=UserProfileCreate(
            whatsapp_number="+2348123456789", first_name="Pay", last_name="Tester"
        )
    )
    return await user_service.create(db, user_in=user_in)


@pytest.mark.asyncio
async def test_create_payment_intent(db: AsyncSession, test_user_for_payment):
    """Test creating a payment record."""
    pay_in = PaymentCreate(
        amount=50000,
        currency="NGN",
        status="pending",
        reference="REF123",
        provider="paystack",
    )

    payment = await payment_service.create_payment_intent(
        db, user_id=test_user_for_payment.id, obj_in=pay_in
    )

    assert payment is not None
    assert payment.reference == "REF123"
    assert payment.status == "pending"


@pytest.mark.asyncio
async def test_verify_payment(db: AsyncSession, test_user_for_payment):
    """Test updating payment status after verification."""
    pay_in = PaymentCreate(amount=50000, status="pending", reference="REF_VERIFY")
    await payment_service.create_payment_intent(
        db, user_id=test_user_for_payment.id, obj_in=pay_in
    )

    now = datetime.now(UTC)
    update_in = PaymentUpdate(status="successful", completed_at=now)
    verified_pay = await payment_service.verify_payment(
        db, reference="REF_VERIFY", obj_in=update_in
    )

    assert verified_pay.status == "successful"
    assert verified_pay.completed_at == now
