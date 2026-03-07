from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.medication import MedicationForm
from app.schemas.medication import MedicationCreate, MedicationScheduleCreate
from app.schemas.reminder import ReminderLogCreate, ReminderLogUpdate
from app.schemas.user import UserCreate, UserProfileCreate
from app.services.medication import medication_service
from app.services.reminder_service import reminder_service
from app.services.user_service import user_service


@pytest.fixture
async def medication_with_schedule(db: AsyncSession):
    # Setup a user and medication first
    user_in = UserCreate(
        profile=UserProfileCreate(
            whatsapp_number="+2349000000001", first_name="Reminder", last_name="Tester"
        )
    )
    user = await user_service.create(db, user_in=user_in)

    med_in = MedicationCreate(
        name="Aspirin",
        medication_form=MedicationForm.TABLET,
        times_per_day=1,
        schedules=[MedicationScheduleCreate(scheduled_time=datetime.now(UTC).time())],
    )
    medication = await medication_service.create_medication(
        db, user_id=user.id, obj_in=med_in
    )
    return user, medication


@pytest.mark.asyncio
async def test_create_reminder_log(db: AsyncSession, medication_with_schedule):
    user, medication = medication_with_schedule
    schedule = medication.schedules[0]

    scheduled_for = datetime.now(UTC) + timedelta(hours=1)
    log_in = ReminderLogCreate(
        schedule_id=schedule.id,
        user_id=user.id,
        scheduled_for=scheduled_for,
        status="pending",
    )

    log = await reminder_service.create_reminder_log(db, obj_in=log_in)

    assert log is not None
    assert log.status == "pending"
    assert log.schedule_id == schedule.id
    assert log.user_id == user.id


@pytest.mark.asyncio
async def test_get_due_reminders(db: AsyncSession, medication_with_schedule):
    user, medication = medication_with_schedule
    schedule = medication.schedules[0]

    # Create a reminder due in the past
    past_due = datetime.now(UTC) - timedelta(minutes=5)
    log_in = ReminderLogCreate(
        schedule_id=schedule.id,
        user_id=user.id,
        scheduled_for=past_due,
        status="pending",
    )
    await reminder_service.create_reminder_log(db, obj_in=log_in)

    # Create a future reminder (not due)
    future_due = datetime.now(UTC) + timedelta(hours=1)
    future_log_in = ReminderLogCreate(
        schedule_id=schedule.id,
        user_id=user.id,
        scheduled_for=future_due,
        status="pending",
    )
    await reminder_service.create_reminder_log(db, obj_in=future_log_in)

    due_reminders = await reminder_service.get_due_reminders(db)

    assert len(due_reminders) >= 1

    user_due = [r for r in due_reminders if r.user_id == user.id]
    assert len(user_due) == 1
    assert user_due[0].status == "queued"


@pytest.mark.asyncio
async def test_update_reminder_status(db: AsyncSession, medication_with_schedule):
    user, medication = medication_with_schedule
    schedule = medication.schedules[0]

    log_in = ReminderLogCreate(
        schedule_id=schedule.id,
        user_id=user.id,
        scheduled_for=datetime.now(UTC),
        status="pending",
    )
    log = await reminder_service.create_reminder_log(db, obj_in=log_in)

    now = datetime.now(UTC)
    update_in = ReminderLogUpdate(status="sent", sent_at=now)
    updated_log = await reminder_service.update_reminder_status(
        db, log_id=log.id, obj_in=update_in
    )

    assert updated_log.status == "sent"
    assert updated_log.sent_at == now
