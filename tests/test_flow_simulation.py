from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.user import UserCreate, UserProfileCreate
from app.services.intent_service import intent_service
from app.services.message_types import ListMsg
from app.services.user_service import user_service


@pytest.fixture
async def sim_user(db: AsyncSession):
    user_in = UserCreate(
        profile=UserProfileCreate(
            whatsapp_number="+2349000000001", first_name="Flow", last_name="Tester"
        )
    )
    return await user_service.create(db, user_in=user_in)


@pytest.mark.asyncio
async def test_medication_flow_simulation(db: AsyncSession, sim_user):
    """Simulate a full medication addition flow."""
    whatsapp_number = sim_user.profile.whatsapp_number

    with (
        patch("app.services.intent_service._get_state_service") as mock_get_state,
        patch(
            "app.services.intent_service.whatsapp_service.send", new_callable=AsyncMock
        ) as mock_send,
    ):
        mock_state_svc = AsyncMock()
        mock_get_state.return_value = mock_state_svc

        mock_send.return_value = ("MOCK_ID", [])

        mock_state_svc.get_state.return_value = {"state": "idle", "data": {}}

        await intent_service.handle_message(db, whatsapp_number, "menu_medication")

        mock_send.assert_called()
        args, kwargs = mock_send.call_args
        msg = args[1]
        assert "What is the *name* of your medication?" in msg.body

        mock_state_svc.get_state.return_value = {"state": "med_name", "data": {}}
        await intent_service.handle_message(db, whatsapp_number, "Paracetamol")

        args, kwargs = mock_send.call_args
        msg = args[1]
        assert isinstance(msg, ListMsg)
        assert "What form is your medication?" in msg.body

        mock_state_svc.get_state.return_value = {
            "state": "med_form",
            "data": {"name": "Paracetamol"},
        }
        await intent_service.handle_message(db, whatsapp_number, "form_tablet")

        args, kwargs = mock_send.call_args
        msg = args[1]
        assert "How many tablets" in msg.body
        assert "Paracetamol" in str(mock_state_svc.set_state.call_args)

        mock_state_svc.get_state.return_value = {
            "state": "med_dosage",
            "data": {"name": "Paracetamol", "form": "tablet"},
        }
        await intent_service.handle_message(db, whatsapp_number, "500mg")

        args, kwargs = mock_send.call_args
        msg = args[1]
        assert "What *time* should I remind you?" in msg.body

        mock_state_svc.get_state.return_value = {
            "state": "med_time",
            "data": {"name": "Paracetamol", "form": "tablet", "dosage": "500mg"},
        }
        await intent_service.handle_message(db, whatsapp_number, "08:00")

        args, kwargs = mock_send.call_args
        msg = args[1]
        assert "Paracetamol" in msg.body
        assert "saved" in msg.body.lower()

        mock_state_svc.clear_state.assert_called_with(whatsapp_number)
