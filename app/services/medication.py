from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.medication import Medication, MedicationSchedule
from app.schemas.medication import MedicationCreate, MedicationUpdate
from app.services.subscription_service import subscription_service
from app.services.user_service import user_service


class MedicationService:
    async def create_medication(
        self, db: AsyncSession, *, user_id: UUID, obj_in: MedicationCreate
    ) -> Medication:
        """Create a new medication and its associated schedules for a user."""
        # 0. Enforce Trial & Subscription logic
        user = await user_service.get_user(db, user_id=user_id)
        if not user or not await subscription_service.can_access_medications(db, user):
            raise ValueError(
                "Your 3-day free trial has expired. "
                "Please subscribe for just ₦500/month to add more medications."
            )

        medication_data = obj_in.model_dump(exclude={"schedules"})
        new_medication = Medication(user_id=user_id, **medication_data)
        db.add(new_medication)
        await db.flush()

        for schedule_in in obj_in.schedules:
            new_schedule = MedicationSchedule(
                medication_id=new_medication.id,
                scheduled_time=schedule_in.scheduled_time,
            )
            db.add(new_schedule)

        await db.commit()
        await db.refresh(new_medication)
        return await self.get_medication_by_id(db, new_medication.id)

    async def get_medication_by_id(
        self, db: AsyncSession, medication_id: UUID
    ) -> Medication | None:
        """Get a medication with its schedules."""
        query = (
            select(Medication)
            .options(selectinload(Medication.schedules))
            .where(Medication.id == medication_id)
        )
        result = await db.execute(query)
        return result.scalars().first()

    async def get_user_medications(
        self, db: AsyncSession, user_id: UUID
    ) -> list[Medication]:
        """Get all active medications for a user."""
        query = (
            select(Medication)
            .options(selectinload(Medication.schedules))
            .where(Medication.user_id == user_id, Medication.is_active.is_(True))
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def update_medication(
        self, db: AsyncSession, medication_id: UUID, obj_in: MedicationUpdate
    ) -> Medication | None:
        """Update medication fields."""
        db_obj = await self.get_medication_by_id(db, medication_id)
        if not db_obj:
            return None

        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return await self.get_medication_by_id(db, medication_id)

    async def deactivate_medication(
        self, db: AsyncSession, medication_id: UUID
    ) -> Medication | None:
        """Soft delete — sets is_active=False instead of deleting the row."""
        db_obj = await self.get_medication_by_id(db, medication_id)
        if not db_obj:
            return None

        db_obj.is_active = False
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def get_medications_due_for_refill(
        self, db: AsyncSession, user_id: UUID, days_ahead: int = 3
    ) -> list[Medication]:
        """Fetch medications where refill is due within N days — used by Celery."""
        now = datetime.now(UTC)
        cutoff = now + timedelta(days=days_ahead)

        query = (
            select(Medication)
            .options(selectinload(Medication.schedules))
            .where(
                Medication.user_id == user_id,
                Medication.is_active.is_(True),
                Medication.next_refill_date <= cutoff,
            )
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_expired_medications(
        self, db: AsyncSession, current_time: datetime | None = None
    ) -> list[Medication]:
        """Fetch active medications whose treatment end date has passed."""
        if current_time is None:
            current_time = datetime.now(UTC)

        query = select(Medication).where(
            Medication.is_active.is_(True),
            Medication.treatment_end_date.isnot(None),
            Medication.treatment_end_date <= current_time,
        )
        result = await db.execute(query)
        return list(result.scalars().all())


medication_service = MedicationService()
