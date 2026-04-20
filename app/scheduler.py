import asyncio
import logging
import threading
from uuid import UUID

from celery import Celery
from celery.schedules import crontab

from app.config import settings
from app.database import async_session
from app.schemas.reminder import ReminderLogUpdate
from app.services.message_types import Button, ButtonMsg
from app.services.reminder_service import reminder_service
from app.services.whatsapp_service import whatsapp_service

logger = logging.getLogger(__name__)

# Initialize Celery
celery_app = Celery(
    "remindam",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

# Optional configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "check-reminders-every-minute": {
            "task": "app.scheduler.check_for_due_reminders",
            "schedule": crontab(minute="*"),  # Every minute
        },
        "generate-future-reminders-hourly": {
            "task": "app.scheduler.generate_future_reminders_task",
            "schedule": crontab(minute="0"),  # Every hour
        },
    },
)


_loop_local = threading.local()


def run_async(coro):
    """
    Helper to run async code in a sync Celery task.
    Uses a persistent thread-local event loop. This prevents SQLAlchemy asyncpg
    connection pool cleanup issues that occur when asyncio.run() constantly
    creates and destroys loops across sequential task executions.
    """
    loop = getattr(_loop_local, "loop", None)
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _loop_local.loop = loop
    return loop.run_until_complete(coro)


@celery_app.task(name="app.scheduler.check_for_due_reminders")
def check_for_due_reminders():
    """
    Producer Task:
    1. Finds all reminders that are 'pending' and past their 'scheduled_for' time.
    2. Queues a 'send_whatsapp_task' for each one.
    """
    logger.info("Checking for due reminders...")

    async def get_and_queue():
        async with async_session() as db:
            due_reminders = await reminder_service.get_due_reminders(db)
            if not due_reminders:
                logger.debug("No due reminders found.")
                return

            logger.info(f"Found {len(due_reminders)} due reminders. Queuing tasks...")
            for reminder in due_reminders:
                send_whatsapp_task.delay(str(reminder.id))

    run_async(get_and_queue())


@celery_app.task(name="app.scheduler.generate_future_reminders_task")
def generate_future_reminders_task():
    """
    Periodic Task:
    Generates missing ReminderLog entries for all active
    schedules for the next 48 hours.
    """
    logger.info("Generating future reminders...")

    async def generate():
        async with async_session() as db:
            await reminder_service.generate_future_reminders(db, days_ahead=2)
            logger.info("Successfully generated future reminders.")

    run_async(generate())


@celery_app.task(name="app.scheduler.send_whatsapp_task")
def send_whatsapp_task(reminder_log_id: str):
    """
    Consumer Task:
    1. Fetches the ReminderLog.
    2. Sends the WhatsApp message using Content Templates.
    3. Logs metadata to DB.
    4. Updates Reminder status to 'sent'.
    """
    logger.info(f"Processing reminder log ID: {reminder_log_id}")

    async def process_reminder():
        async with async_session() as db:
            from datetime import UTC, datetime

            from sqlalchemy import select
            from sqlalchemy.orm import selectinload

            from app.models.medication import MedicationSchedule
            from app.models.reminder import ReminderLog
            from app.models.user import User

            query = (
                select(ReminderLog)
                .options(
                    selectinload(ReminderLog.schedule).selectinload(
                        MedicationSchedule.medication
                    ),
                    selectinload(ReminderLog.user).selectinload(User.profile),
                )
                .where(ReminderLog.id == UUID(reminder_log_id))
            )
            result = await db.execute(query)
            reminder = result.scalars().first()

            if not reminder or reminder.status != "queued":
                logger.warning(f"Reminder {reminder_log_id} not found or not queued.")
                return

            user = reminder.user
            med = reminder.schedule.medication

            first_name = user.profile.first_name
            if not first_name or first_name.strip().lower() == "new":
                name_display = ""
            else:
                name_display = first_name.strip()

            item_type = getattr(med, "item_type", "medication")
            msg = None

            if item_type == "exercise":
                duration_str = f" ({med.dosage})" if med.dosage else ""
                msg = ButtonMsg(
                    body=(
                        f"🏃 Hey {name_display}, it's time for your "
                        f"*{med.name}*{duration_str}! Let's go! 💪"
                    ),
                    buttons=[
                        Button(id=f"take_{reminder.id}", text="✅ Done"),
                        Button(id=f"snooze_{reminder.id}", text="⏰ Snooze (3m)"),
                        Button(id=f"skip_{reminder.id}", text="❌ Skip"),
                    ],
                    content_sid=settings.CT_REMINDER_EXERCISE,
                    content_variables={
                        "1": name_display or "there",
                        "2": med.name,
                    },
                )

            elif item_type == "water_intake":
                amount = med.dosage or "some water"
                msg = ButtonMsg(
                    body=(
                        f"💧 Hey {name_display}, time to drink "
                        f"*{amount}* of water! Stay hydrated! 🥤"
                    ),
                    buttons=[
                        Button(id=f"take_{reminder.id}", text="✅ Done"),
                        Button(id=f"snooze_{reminder.id}", text="⏰ Snooze (3m)"),
                        Button(id=f"skip_{reminder.id}", text="❌ Skip"),
                    ],
                    content_sid=settings.CT_REMINDER_WATER,
                    content_variables={
                        "1": name_display or "there",
                        "2": amount,
                    },
                )

            else:
                # Default: medication
                dosage_val = ""
                if med.dosage_amount:
                    amount_str = f"{med.dosage_amount:g}"
                    unit_str = med.dosage_unit or med.medication_form or ""
                    dosage_val = f"{amount_str} {unit_str}".strip()
                elif med.dosage:
                    dosage_val = med.dosage

                msg = ButtonMsg(
                    body=(
                        f"💊 Hello {name_display}, it's time to take "
                        f"*{dosage_val}* of *{med.name}*. "
                        "Stay healthy! ❤️"
                    ),
                    buttons=[
                        Button(id=f"take_{reminder.id}", text="✅ Taken"),
                        Button(id=f"snooze_{reminder.id}", text="⏰ Snooze (3m)"),
                        Button(id=f"skip_{reminder.id}", text="❌ Skip"),
                    ],
                    content_sid=settings.CT_REMINDER_MEDICATION,
                    content_variables={
                        "1": name_display or "there",
                        "2": dosage_val or "your dose",
                        "3": med.name,
                    },
                )

            msg_id = await whatsapp_service.send(
                user.profile.whatsapp_number,
                msg,
                db=db,
                user_id=user.id,
                reminder_log_id=reminder.id,
            )

            # Store last reminder ID so the flow engine can map
            # template button IDs (take_action) → take_{uuid}
            if msg_id:
                try:
                    from app.services.state_service import state_service

                    await state_service.update_data(
                        user.profile.whatsapp_number,
                        "_last_reminder_id",
                        str(reminder.id),
                    )
                except Exception:
                    logger.warning("Redis unavailable, last_reminder_id not saved")

            if msg_id:
                await reminder_service.update_reminder_status(
                    db,
                    log_id=reminder.id,
                    obj_in=ReminderLogUpdate(status="sent", sent_at=datetime.now(UTC)),
                )
                logger.info(f"Successfully sent reminder {reminder_log_id}")
            else:
                await reminder_service.update_reminder_status(
                    db, log_id=reminder.id, obj_in=ReminderLogUpdate(status="failed")
                )
                logger.error(f"Failed to send WhatsApp for reminder {reminder_log_id}")

    run_async(process_reminder())
