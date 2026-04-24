import hashlib
import hmac
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.schemas.payment import PaymentUpdate
from app.services.payment_service import payment_service
from app.services.subscription_service import subscription_service

logger = logging.getLogger(__name__)


def verify_paystack_webhook(payload: bytes, signature: str) -> bool:
    """Verify that a webhook request is genuinely from Paystack.

    Paystack signs webhooks with HMAC-SHA512 using your secret key.
    See: https://paystack.com/docs/payments/webhooks/#verify-event-origin
    """
    if not settings.PAYSTACK_SECRET_KEY:
        logger.warning("PAYSTACK_SECRET_KEY is not set. Cannot verify webhook.")
        return False

    expected = hmac.HMAC(
        settings.PAYSTACK_SECRET_KEY.encode("utf-8"),
        payload,
        hashlib.sha512,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


async def process_successful_payment(
    db: AsyncSession,
    reference: str,
) -> bool:
    """Handle a successful Paystack payment.

    1. Update payment status to 'successful'.
    2. Activate the linked subscription (if any).

    Returns True if processed successfully, False otherwise.
    """
    now = datetime.now(UTC)

    updated_payment = await payment_service.verify_payment(
        db,
        reference=reference,
        obj_in=PaymentUpdate(status="successful", completed_at=now),
    )

    if not updated_payment:
        logger.error(f"Payment with reference '{reference}' not found.")
        return False

    if updated_payment.subscription_id:
        from app.schemas.subscription import SubscriptionUpdate

        await subscription_service.update_subscription(
            db,
            sub_id=updated_payment.subscription_id,
            obj_in=SubscriptionUpdate(
                status="active",
                starts_at=now,
                expires_at=now + timedelta(days=30),
            ),
        )
        logger.info(
            f"Activated subscription {updated_payment.subscription_id} "
            f"for payment {reference}."
        )
    else:
        from app.schemas.subscription import SubscriptionCreate

        plan_name = "standard"
        if updated_payment.amount >= settings.SUBSCRIPTION_AMOUNT_PREMIUM_KOBO:
            plan_name = "premium"

        new_sub = await subscription_service.create_subscription(
            db,
            user_id=updated_payment.user_id,
            obj_in=SubscriptionCreate(
                amount_kobo=updated_payment.amount,
                plan=plan_name,
                status="active",
                starts_at=now,
                expires_at=now + timedelta(days=30),
                auto_renew=False,
            ),
        )
        updated_payment.subscription_id = new_sub.id
        db.add(updated_payment)
        await db.commit()
        logger.info(
            f"Created new {plan_name} subscription {new_sub.id} "
            f"for payment {reference}."
        )

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models.user import User
    from app.services.message_types import Button, ButtonMsg
    from app.services.whatsapp_service import whatsapp_service

    user_query = (
        select(User)
        .options(selectinload(User.profile))
        .where(User.id == updated_payment.user_id)
    )
    user = (await db.execute(user_query)).scalars().first()

    if user and user.profile:
        msg = ButtonMsg(
            body=(
                "🎉 *Payment Successful!*\n\n"
                "Your Premium Subscription is now active! "
                "You now have full access to Exercise Reminders, "
                "Water Intake, and Adherence Reports."
            ),
            buttons=[Button(id="go_menu", text="🏠 Main Menu")],
        )
        await whatsapp_service.send(
            user.profile.whatsapp_number, msg, db=db, user_id=user.id
        )

    return True
