from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.user import UserCreate, UserProfileCreate
from app.services.user_service import user_service


@pytest.fixture
def sample_user_create() -> UserCreate:
    return UserCreate(
        profile=UserProfileCreate(
            whatsapp_number="+2349000000001",
            first_name="SoftDel",
            last_name="Tester",
        )
    )


# ── 1. Soft delete sets is_active=False and deleted_at correctly ──


@pytest.mark.asyncio
async def test_soft_delete_sets_fields(
    db: AsyncSession, sample_user_create: UserCreate
):
    """Soft delete must set is_active=False and populate deleted_at."""
    user = await user_service.create(db, user_in=sample_user_create)
    assert user.is_active is True
    assert user.deleted_at is None

    deleted = await user_service.soft_delete(db, user.id)
    assert deleted.is_active is False
    assert deleted.deleted_at is not None


# ── 2. Getters exclude deleted users by default ──


@pytest.mark.asyncio
async def test_get_by_id_excludes_deleted(
    db: AsyncSession, sample_user_create: UserCreate
):
    """get_by_id must return None for soft-deleted users by default."""
    user = await user_service.create(db, user_in=sample_user_create)
    await user_service.soft_delete(db, user.id)

    assert await user_service.get_by_id(db, user.id) is None
    assert await user_service.get_by_id(db, user.id, include_deleted=True) is not None


@pytest.mark.asyncio
async def test_get_by_whatsapp_excludes_deleted(
    db: AsyncSession, sample_user_create: UserCreate
):
    """get_by_whatsapp_number must return None for soft-deleted users by default."""
    user = await user_service.create(db, user_in=sample_user_create)
    phone = user.profile.whatsapp_number
    await user_service.soft_delete(db, user.id)

    assert await user_service.get_by_whatsapp_number(db, phone) is None
    found = await user_service.get_by_whatsapp_number(db, phone, include_deleted=True)
    assert found is not None


# ── 3. Webhook rejects deleted user's message ──


@pytest.mark.asyncio
async def test_webhook_rejects_deleted_user(
    db: AsyncSession, sample_user_create: UserCreate
):
    """A soft-deleted user messaging the bot receives the deregistration notice."""
    from app.services.intent_service import intent_service

    user = await user_service.create(db, user_in=sample_user_create)
    phone = user.profile.whatsapp_number
    await user_service.soft_delete(db, user.id)

    with patch("app.services.intent_service.whatsapp_service") as mock_wa:
        mock_wa.send = AsyncMock()
        await intent_service.handle_message(db, phone, "hello")

        mock_wa.send.assert_called_once()
        sent_msg = mock_wa.send.call_args[0][1]
        assert "no longer registered" in sent_msg.body.lower()


# ── 4. RESTORE keyword reactivates within 90 days ──


@pytest.mark.asyncio
async def test_restore_within_window(db: AsyncSession, sample_user_create: UserCreate):
    """RESTORE keyword within 90 days reactivates the account."""
    user = await user_service.create(db, user_in=sample_user_create)
    await user_service.soft_delete(db, user.id)

    restored = await user_service.restore_account(db, user.id)
    assert restored is not None
    assert restored.is_active is True
    assert restored.deleted_at is None


@pytest.mark.asyncio
async def test_restore_via_webhook(db: AsyncSession, sample_user_create: UserCreate):
    """RESTORE keyword via the webhook reactivates the account."""
    from app.services.intent_service import intent_service

    user = await user_service.create(db, user_in=sample_user_create)
    phone = user.profile.whatsapp_number
    await user_service.soft_delete(db, user.id)

    with patch("app.services.intent_service.whatsapp_service") as mock_wa:
        mock_wa.send = AsyncMock()
        await intent_service.handle_message(db, phone, "RESTORE")

        mock_wa.send.assert_called_once()
        sent_msg = mock_wa.send.call_args[0][1]
        assert "reactivated" in sent_msg.body.lower()


# ── 5. RESTORE after 90 days returns registration prompt ──


@pytest.mark.asyncio
async def test_restore_after_90_days_fails(
    db: AsyncSession, sample_user_create: UserCreate
):
    """RESTORE beyond the 90-day window must fail."""
    user = await user_service.create(db, user_in=sample_user_create)
    await user_service.soft_delete(db, user.id)

    user.deleted_at = datetime.now(UTC) - timedelta(days=91)
    db.add(user)
    await db.commit()

    restored = await user_service.restore_account(db, user.id)
    assert restored is None


# ── 6. Cleanup task identifies and hard-deletes expired users ──


@pytest.mark.asyncio
async def test_cleanup_deletes_expired_users(
    db: AsyncSession, sample_user_create: UserCreate
):
    from app.scheduler import perform_cleanup

    user = await user_service.create(db, user_in=sample_user_create)
    await user_service.soft_delete(db, user.id)

    user.deleted_at = datetime.now(UTC) - timedelta(days=91)
    db.add(user)
    await db.commit()

    await perform_cleanup(db)

    db.expire_all()
    assert await user_service.get_by_id(db, user.id, include_deleted=True) is None


# ── 7. Cleanup task is idempotent ──


@pytest.mark.asyncio
async def test_cleanup_idempotent(db: AsyncSession, sample_user_create: UserCreate):
    from app.scheduler import perform_cleanup

    user = await user_service.create(db, user_in=sample_user_create)
    await user_service.soft_delete(db, user.id)

    user.deleted_at = datetime.now(UTC) - timedelta(days=91)
    db.add(user)
    await db.commit()

    await perform_cleanup(db)

    db.expire_all()
    assert await user_service.get_by_id(db, user.id, include_deleted=True) is None

    # Should safely no-op
    await perform_cleanup(db)


# ── 8. Payment logs are nullified, not deleted ──


@pytest.mark.asyncio
async def test_payment_logs_nullified_after_hard_delete(
    db: AsyncSession, sample_user_create: UserCreate
):
    """Hard-deleting a user must SET NULL on payment.user_id, not delete the payment."""
    from app.models.payment import Payment

    user = await user_service.create(db, user_in=sample_user_create)

    payment = Payment(
        user_id=user.id,
        amount=50000,
        currency="NGN",
        status="successful",
        reference="test_ref_soft_del_001",
        provider="paystack",
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    payment_id = payment.id

    await db.delete(user)
    await db.commit()

    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    remaining_payment = result.scalars().first()
    assert remaining_payment is not None
    assert remaining_payment.user_id is None


# ── 9. 7-day warning sent to correct users only ──


@pytest.mark.asyncio
async def test_deletion_warning_targets_correct_window(
    db: AsyncSession, sample_user_create: UserCreate
):
    from app.scheduler import perform_notification

    user = await user_service.create(db, user_in=sample_user_create)
    await user_service.soft_delete(db, user.id)

    target_date = datetime.now(UTC) - timedelta(days=85, hours=12)
    user.deleted_at = target_date
    db.add(user)
    await db.commit()

    await perform_notification(db)

    db.expire_all()
    await db.refresh(user)
    assert user.deletion_warning_sent_at is not None
