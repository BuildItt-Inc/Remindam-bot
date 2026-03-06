import asyncio
import logging
from uuid import UUID

from celery import Celery
from celery.schedules import crontab

from app.config import settings
from app.database import async_session
from app.schemas.reminder import ReminderLogUpdate
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
    # For a project of this size, we can keep the frequency high
    beat_schedule={
        "check-reminders-every-minute": {
            "task": "app.scheduler.check_for_due_reminders",
            "schedule": crontab(minute="*"),  # Every minute
        },
    },
)


def run_async(coro):
    """Helper to run async code in a sync Celery task."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        # This shouldn't happen in a standard Celery worker, but good to be safe
        return asyncio.ensure_future(coro, loop=loop)
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
                # Trigger individual consumer task for parallel execution
                send_whatsapp_task.delay(str(reminder.id))

    run_async(get_and_queue())


@celery_app.task(name="app.scheduler.send_whatsapp_task")
def send_whatsapp_task(reminder_log_id: str):
    """
    Consumer Task:
    1. Fetches the ReminderLog.
    2. Sends the WhatsApp message.
    3. Logs metadata to DB.
    4. Updates Reminder status to 'sent'.
    """
    logger.info(f"Processing reminder log ID: {reminder_log_id}")

    async def process_reminder():
        async with async_session() as db:
            # 1. Fetch reminder with related data (joined in service)
            from datetime import UTC, datetime

            from sqlalchemy import select
            from sqlalchemy.orm import selectinload

            from app.models.medication import MedicationSchedule
            from app.models.reminder import ReminderLog
            from app.models.user import User

            # Re-fetch to ensure we have fresh session data
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

            if not reminder or reminder.status != "pending":
                logger.warning(f"Reminder {reminder_log_id} not found or not pending.")
                return

            user = reminder.user
            med = reminder.schedule.medication

            # 2. Build Message
            message_body = (
                f"Hello {user.profile.first_name}, it's time for your "
                f"{med.name} ({med.dosage})."
            )

            # 3. Send WhatsApp (Mocked or Real based on .env)
            # This service method also logs to MessageLog DB if db is provided
            twilio_sid = await whatsapp_service.send_message(
                to_number=user.profile.whatsapp_number,
                message=message_body,
                db=db,
                user_id=user.id,
                reminder_log_id=reminder.id,
            )

            # 4. Update status
            if twilio_sid:
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
