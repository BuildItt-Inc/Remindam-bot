from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import Subscription
from app.schemas.subscription import SubscriptionCreate, SubscriptionUpdate


class SubscriptionService:
    async def get_user_subscription(
        self, db: AsyncSession, user_id: UUID
    ) -> Subscription | None:
        """Get the active subscription for a user."""
        query = select(Subscription).where(
            Subscription.user_id == user_id, Subscription.status == "active"
        )
        result = await db.execute(query)
        return result.scalars().first()

    async def create_subscription(
        self, db: AsyncSession, *, user_id: UUID, obj_in: SubscriptionCreate
    ) -> Subscription:
        """Create a new subscription record."""
        new_sub = Subscription(user_id=user_id, **obj_in.model_dump())
        db.add(new_sub)
        await db.commit()
        await db.refresh(new_sub)
        return new_sub

    async def update_subscription(
        self, db: AsyncSession, *, sub_id: UUID, obj_in: SubscriptionUpdate
    ) -> Subscription | None:
        """Update a subscription record."""
        query = select(Subscription).where(Subscription.id == sub_id)
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


subscription_service = SubscriptionService()
