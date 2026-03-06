import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.database import async_session
from app.models.reminder import ReminderLog
from app.scheduler import check_for_due_reminders, send_whatsapp_task
from app.schemas.medication import MedicationCreate, MedicationScheduleCreate
from app.schemas.user import UserCreate, UserProfileCreate
from app.services.medication import medication_service
from app.services.reminder_service import reminder_service
from app.services.user_service import user_service


async def verify():
    print("--- Starting Celery Task Verification ---")

    async with async_session() as db:
        # 1. Setup Data
        user_in = UserCreate(
            profile=UserProfileCreate(
                whatsapp_number="+234555666777", first_name="Celery", last_name="Tester"
            )
        )
        user = await user_service.create(db, user_in=user_in)

        med_in = MedicationCreate(
            name="Vitamin C",
            times_per_day=1,
            schedules=[
                MedicationScheduleCreate(
                    scheduled_time=(datetime.now(UTC) - timedelta(minutes=10)).time()
                )
            ],
        )
        medication = await medication_service.create_medication(
            db, user_id=user.id, obj_in=med_in
        )

        from app.schemas.reminder import ReminderLogCreate

        log_in = ReminderLogCreate(
            user_id=user.id,
            schedule_id=medication.schedules[0].id,
            status="pending",
            scheduled_for=datetime.now(UTC) - timedelta(minutes=5),
        )
        pending_log = await reminder_service.create_reminder_log(db, obj_in=log_in)
        pending_id = str(pending_log.id)
        print(f"Created pending reminder: {pending_id}")

    print("Running check_for_due_reminders logic...")

    check_for_due_reminders()

    print(f"Running send_whatsapp_task logic for {pending_id}...")
    send_whatsapp_task(pending_id)

    async with async_session() as db:
        from sqlalchemy import select

        from app.models.message import MessageLog

        # Check reminder status
        res = await db.execute(
            select(ReminderLog).where(ReminderLog.id == UUID(pending_id))
        )
        log = res.scalars().first()
        print(f"Final Reminder Status: {log.status}")
        assert log.status == "sent"

        # Check message log
        res = await db.execute(
            select(MessageLog).where(MessageLog.reminder_log_id == UUID(pending_id))
        )
        msg = res.scalars().first()
        print(f"Message Log Created: {msg is not None}")
        assert msg is not None
        assert msg.status == "sent"

    print("--- Celery Task Verification SUCCESS ---")


if __name__ == "__main__":
    asyncio.run(verify())
