import hashlib
import hmac
import logging
from datetime import UTC, datetime

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

    expected = hmac.new(
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
            obj_in=SubscriptionUpdate(status="active"),
        )
        logger.info(
            f"Activated subscription {updated_payment.subscription_id} "
            f"for payment {reference}."
        )

    return True
