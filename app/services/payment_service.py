import logging
import secrets
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.payment import Payment
from app.schemas.payment import PaymentCreate, PaymentUpdate

logger = logging.getLogger(__name__)


class PaymentService:
    async def create_payment_intent(
        self, db: AsyncSession, *, user_id: UUID, obj_in: PaymentCreate
    ) -> Payment:
        """Create a new payment record (e.g. before redirecting to payment gateway)."""
        new_payment = Payment(user_id=user_id, **obj_in.model_dump())
        db.add(new_payment)
        await db.commit()
        await db.refresh(new_payment)
        return new_payment

    async def verify_payment(
        self, db: AsyncSession, *, reference: str, obj_in: PaymentUpdate
    ) -> Payment | None:
        """Update a payment record status after gateway callback/webhook."""
        query = select(Payment).where(Payment.reference == reference)
        result = await db.execute(query)
        db_obj = result.scalars().first()

        if not db_obj:
            return None

        if db_obj.status == "successful":
            logger.info("Payment %s already processed, skipping.", reference)
            return db_obj

        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def initialize_transaction(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        email: str,
        amount_kobo: int,
        subscription_id: UUID | None = None,
    ) -> str | None:
        """Initialize a Paystack transaction and return the checkout URL."""
        if not settings.PAYSTACK_SECRET_KEY:
            logger.error("PAYSTACK_SECRET_KEY not set")
            return None

        reference = f"rem_{secrets.token_hex(8)}"

        url = "https://api.paystack.co/transaction/initialize"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "email": email,
            "amount": amount_kobo,
            "reference": reference,
            "metadata": {
                "user_id": str(user_id),
                "subscription_id": str(subscription_id) if subscription_id else None,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            payment_in = PaymentCreate(
                amount=amount_kobo,
                reference=reference,
                status="pending",
                provider="paystack",
                subscription_id=subscription_id,
            )
            await self.create_payment_intent(db, user_id=user_id, obj_in=payment_in)

            return data.get("data", {}).get("authorization_url")

        except Exception as e:
            logger.error(f"Failed to initialize Paystack transaction: {e}")
            return None


payment_service = PaymentService()
