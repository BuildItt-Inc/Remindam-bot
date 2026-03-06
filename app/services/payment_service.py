from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment
from app.schemas.payment import PaymentCreate, PaymentUpdate


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

        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj


payment_service = PaymentService()
