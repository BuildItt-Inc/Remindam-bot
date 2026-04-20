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

        # Use SKIP LOCKED to safely grab reminders without blocking other workers
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
            .with_for_update(skip_locked=True)
            .limit(100)  # Process in batches to avoid locking too many rows
        )
        result = await db.execute(query)
        reminders = list(result.scalars().all())

        # Mark them as "queued" to prevent other producers/consumers from getting them
        for reminder in reminders:
            reminder.status = "queued"
            db.add(reminder)

        if reminders:
            await db.commit()

        return reminders

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

    async def generate_future_reminders(
        self, db: AsyncSession, user_id: UUID | None = None, days_ahead: int = 2
    ):
        """Pre-generate ReminderLog entries for active medication schedules."""
        import zoneinfo
        from datetime import timedelta

        from app.models.medication import Medication

        now = datetime.now(UTC)
        start_date = now.date()
        target_dates = [start_date + timedelta(days=i) for i in range(days_ahead)]

        # Fetch active schedules along with user profiles for timezone info
        query = (
            select(MedicationSchedule)
            .join(Medication)
            .options(
                selectinload(MedicationSchedule.medication)
                .selectinload(Medication.user)
                .selectinload(User.profile)
            )
            .where(
                Medication.is_active.is_(True), MedicationSchedule.is_active.is_(True)
            )
        )
        if user_id:
            query = query.where(Medication.user_id == user_id)

        result = await db.execute(query)
        schedules = result.scalars().all()

        if not schedules:
            return

        # --- BULK FETCH EXPERIMENT ---
        # Cache existing logs for the relevant schedules and time window to prevent N+1 queries.
        now = datetime.now(UTC)
        cutoff = now - timedelta(hours=1)
        max_future = now + timedelta(days=days_ahead + 2)

        schedule_ids = [s.id for s in schedules]
        existing_logs_query = select(ReminderLog.schedule_id, ReminderLog.scheduled_for).where(
            ReminderLog.schedule_id.in_(schedule_ids),
            ReminderLog.scheduled_for >= cutoff,
            ReminderLog.scheduled_for <= max_future,
        )
        existing_logs_result = await db.execute(existing_logs_query)
        existing_set = {(row.schedule_id, row.scheduled_for) for row in existing_logs_result.all()}

        for schedule in schedules:
            med = schedule.medication
            user = med.user

            tz_str = "UTC"
            if user and user.profile and user.profile.timezone:
                tz_str = user.profile.timezone

            try:
                tz = zoneinfo.ZoneInfo(tz_str)
            except Exception:
                tz = UTC

            for t_date in target_dates:
                # Combine date and time in the user's local timezone
                local_dt = datetime.combine(t_date, schedule.scheduled_time).replace(
                    tzinfo=tz
                )

                # Convert the absolute point in time to UTC for the database
                scheduled_for = local_dt.astimezone(UTC)

                # Skip if the scheduled time is already firmly in the past 
                # (more than 1 hour ago)
                if scheduled_for < cutoff:
                    continue

                if (schedule.id, scheduled_for) not in existing_set:
                    new_log = ReminderLog(
                        schedule_id=schedule.id,
                        user_id=med.user_id,
                        scheduled_for=scheduled_for,
                        status="pending",
                    )
                    db.add(new_log)

        await db.commit()


reminder_service = ReminderService()
