from datetime import time

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.medication import (
    MedicationCreate,
    MedicationScheduleCreate,
    MedicationUpdate,
)
from app.schemas.user import UserCreate, UserProfileCreate
from app.services.medication import medication_service
from app.services.user_service import user_service


@pytest.fixture
async def test_user(db: AsyncSession):
    user_in = UserCreate(
        profile=UserProfileCreate(
            whatsapp_number="+2347012345678", first_name="Meds", last_name="Tester"
        )
    )
    return await user_service.create(db, user_in=user_in)


@pytest.fixture
def sample_medication_create() -> MedicationCreate:
    return MedicationCreate(
        name="Paracetamol",
        dosage="500mg",
        times_per_day=2,
        schedules=[
            MedicationScheduleCreate(scheduled_time=time(hour=8, minute=0)),
            MedicationScheduleCreate(scheduled_time=time(hour=20, minute=0)),
        ],
    )


@pytest.mark.asyncio
async def test_create_medication(
    db: AsyncSession, test_user, sample_medication_create: MedicationCreate
):
    """Test creating a medication with multiple schedules."""
    medication = await medication_service.create_medication(
        db, user_id=test_user.id, obj_in=sample_medication_create
    )

    assert medication is not None
    assert medication.name == "Paracetamol"
    assert len(medication.schedules) == 2
    assert medication.schedules[0].scheduled_time == time(8, 0)
    assert medication.user_id == test_user.id


@pytest.mark.asyncio
async def test_get_user_medications(
    db: AsyncSession, test_user, sample_medication_create: MedicationCreate
):
    """Test fetching all active medications for a user."""
    await medication_service.create_medication(
        db, user_id=test_user.id, obj_in=sample_medication_create
    )

    meds = await medication_service.get_user_medications(db, user_id=test_user.id)
    assert len(meds) == 1
    assert meds[0].name == "Paracetamol"


@pytest.mark.asyncio
async def test_update_medication(
    db: AsyncSession, test_user, sample_medication_create: MedicationCreate
):
    """Test updating medication fields (e.g., name, dosage)."""
    med = await medication_service.create_medication(
        db, user_id=test_user.id, obj_in=sample_medication_create
    )

    update_in = MedicationUpdate(name="Panadol", dosage="1000mg")
    updated_med = await medication_service.update_medication(
        db, medication_id=med.id, obj_in=update_in
    )

    assert updated_med.name == "Panadol"
    assert updated_med.dosage == "1000mg"


@pytest.mark.asyncio
async def test_deactivate_medication(
    db: AsyncSession, test_user, sample_medication_create: MedicationCreate
):
    """Test soft delete of a medication."""
    med = await medication_service.create_medication(
        db, user_id=test_user.id, obj_in=sample_medication_create
    )

    await medication_service.deactivate_medication(db, medication_id=med.id)

    # get_user_medications filters by is_active=True
    active_meds = await medication_service.get_user_medications(
        db, user_id=test_user.id
    )
    assert len(active_meds) == 0

    # It should still exist but be inactive
    db_obj = await medication_service.get_medication_by_id(db, medication_id=med.id)
    assert db_obj is not None
    assert db_obj.is_active is False
