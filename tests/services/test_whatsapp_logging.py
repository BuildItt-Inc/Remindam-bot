import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import MessageLog
from app.schemas.user import UserCreate, UserProfileCreate
from app.services.message_types import TextMsg
from app.services.user_service import user_service
from app.services.whatsapp_service import whatsapp_service


@pytest.fixture
async def logging_user(db: AsyncSession):
    user_in = UserCreate(
        profile=UserProfileCreate(
            whatsapp_number="+2348011122233", first_name="Log", last_name="Tester"
        )
    )
    return await user_service.create(db, user_in=user_in)


@pytest.mark.asyncio
async def test_whatsapp_logging_to_db(db: AsyncSession, logging_user):
    """Test that send_message correctly logs metadata to
    the database when a db session is provided."""
    original_mock_mode = whatsapp_service.mock_mode
    whatsapp_service.mock_mode = True

    try:
        sid = await whatsapp_service.send(
            to_number="+2348011122233",
            msg=TextMsg("Test Logging"),
            db=db,
            user_id=logging_user.id,
        )

        assert sid is not None
        assert sid.startswith("MOCK_")

        query = select(MessageLog).where(MessageLog.user_id == logging_user.id)
        result = await db.execute(query)
        log = result.scalars().first()

        assert log is not None
        assert log.provider_message_id == sid
        assert log.status == "sent"
        assert log.direction == "outbound"
        assert not hasattr(log, "content") or log.content is None
    finally:
        whatsapp_service.mock_mode = original_mock_mode
