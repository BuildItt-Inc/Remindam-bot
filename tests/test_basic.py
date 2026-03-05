import pytest
from sqlalchemy import text

from app.database import engine


@pytest.mark.asyncio
async def test_database_connection():
    """Test that the async SQLAlchemy engine can connect to the database."""
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1


def test_models_importable():
    """Test that all database models can be imported without circular dependencies."""
    from app.models.medication import Medication, MedicationSchedule
    from app.models.message import MessageLog
    from app.models.payment import Payment
    from app.models.reminder import ReminderLog
    from app.models.subscription import Subscription
    from app.models.user import User, UserProfile

    assert User is not None
    assert UserProfile is not None
    assert Subscription is not None
    assert Payment is not None
    assert Medication is not None
    assert MedicationSchedule is not None
    assert ReminderLog is not None
    assert MessageLog is not None
