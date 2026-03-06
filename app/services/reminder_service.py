from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.medication import MedicationSchedule
from app.models.reminder import ReminderLog
from app.models.user import User
from app.schemas.reminder import ReminderLogCreate, ReminderLogUpdate


class ReminderService:
    async def create_reminder_log(
        self, db: AsyncSession, *, obj_in: ReminderLogCreate
    ) -> ReminderLog:
        """Create a new reminder log entry (to be processed by Celery)."""
        new_log = ReminderLog(**obj_in.model_dump())
        db.add(new_log)
        await db.commit()
        await db.refresh(new_log)
        return new_log

    async def get_due_reminders(
        self, db: AsyncSession, current_time: datetime | None = None
    ) -> list[ReminderLog]:
        """Fetch all reminders that are due to be sent."""
        if current_time is None:
            current_time = datetime.now(UTC)

        query = (
            select(ReminderLog)
            .options(
                selectinload(ReminderLog.schedule).selectinload(
                    MedicationSchedule.medication
                ),
                selectinload(ReminderLog.user).selectinload(User.profile),
            )
            .where(
                ReminderLog.status == "pending",
                ReminderLog.scheduled_for <= current_time,
            )
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def update_reminder_status(
        self, db: AsyncSession, log_id: UUID, obj_in: ReminderLogUpdate
    ) -> ReminderLog | None:
        """Update the status of a reminder log (e.g. mark as sent or answered)."""
        query = select(ReminderLog).where(ReminderLog.id == log_id)
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


reminder_service = ReminderService()
