from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.subscription import SubscriptionCreate, SubscriptionUpdate


class SubscriptionService:
    def is_trial_active(self, user: User) -> bool:
        """Check if the user's 3-day free trial is still active."""
        if not user.trial_start_date:
            return False

        now = datetime.now(UTC)
        trial_end = user.trial_start_date + timedelta(days=settings.TRIAL_DAYS)
        return now <= trial_end

    async def has_active_subscription(self, db: AsyncSession, user_id: UUID) -> bool:
        """Check if the user has an active, paid subscription."""
        sub = await self.get_user_subscription(db, user_id)
        return sub is not None

    async def can_access_medications(self, db: AsyncSession, user: User) -> bool:
        """
        Medications are available during the free trial
        OR with an active subscription.
        """
        if self.is_trial_active(user):
            return True
        return await self.has_active_subscription(db, user.id)

    async def can_access_reports(self, db: AsyncSession, user_id: UUID) -> bool:
        """
        Adherence reports are ONLY available to paid subscribers
        (not in free trial).
        """
        return await self.has_active_subscription(db, user_id)

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
        """Create a new subscription record. Defaults to ₦500 if not provided."""
        amount = obj_in.amount_kobo or settings.SUBSCRIPTION_AMOUNT_KOBO

        new_sub = Subscription(
            user_id=user_id,
            amount_kobo=amount,
            plan=obj_in.plan,
            status=obj_in.status,
            starts_at=obj_in.starts_at,
            expires_at=obj_in.expires_at,
            auto_renew=obj_in.auto_renew,
            trial_ends_at=obj_in.trial_ends_at,
        )
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
