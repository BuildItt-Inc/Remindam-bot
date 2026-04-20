"""Thin router: incoming message → flow engine → send response.

1. Identifies the user (or creates a new one)
2. Loads conversational state from Redis
3. Delegates to FlowService for the interaction logic
4. Sends the structured response via WhatsAppService
5. Persists the new state back to Redis
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.flow_service import flow_service
from app.services.user_service import user_service
from app.services.whatsapp_service import whatsapp_service

logger = logging.getLogger(__name__)


def _get_state_service():
    from app.services.state_service import state_service

    return state_service


class IntentService:
    async def handle_message(
        self,
        db: AsyncSession,
        whatsapp_number: str,
        message_body: str,
    ) -> None:
        """Process incoming message and send the response."""
        # 1. Find or create user
        user = await user_service.get_by_whatsapp_number(db, whatsapp_number)

        if not user:
            await self._handle_new_user(db, whatsapp_number)
            return

        # 2. Load state from Redis
        try:
            state_svc = _get_state_service()
            state_info = await state_svc.get_state(whatsapp_number)
        except Exception:
            logger.warning("Redis unavailable, defaulting to idle")
            state_info = {"state": "idle", "data": {}}

        state = state_info.get("state", "idle")
        data = state_info.get("data", {})

        # Content API sends button IDs directly (no more numbered mapping needed)
        body = message_body.strip()

        # Map static template button IDs to dynamic ones using the stored reminder ID
        if body in ("take_action", "snooze_action", "skip_action"):
            last_reminder_id = data.get("_last_reminder_id")
            if last_reminder_id:
                action_type = body.split("_")[0]  # 'take', 'snooze', 'skip'
                body = f"{action_type}_{last_reminder_id}"

        # 3. Run flow engine
        response_msg, next_state, state_data = await flow_service.handle(
            db, user, state, data, body
        )

        # 4. Send the response
        await whatsapp_service.send(
            whatsapp_number,
            response_msg,
            db=db,
            user_id=user.id,
        )

        # 5. Persist new state
        try:
            state_svc = _get_state_service()
            if next_state is None:
                await state_svc.clear_state(whatsapp_number)
            else:
                save_data = state_data or {}
                await state_svc.set_state(
                    whatsapp_number,
                    next_state,
                    save_data,
                )
        except Exception:
            logger.warning("Redis unavailable, state not saved")

    async def _handle_new_user(self, db: AsyncSession, whatsapp_number: str) -> None:
        """Create user and send T&C before welcome + main menu."""
        from app.schemas.user import UserCreate, UserProfileCreate
        from app.services.message_types import Button, ButtonMsg

        user_in = UserCreate(
            profile=UserProfileCreate(
                whatsapp_number=whatsapp_number,
                first_name="New",
                last_name="User",
            )
        )
        new_user = await user_service.create(db, user_in=user_in)

        # Send Terms & Conditions using Content Template
        tc_msg = ButtonMsg(
            body=(
                "⚖️ *Medical Disclaimer & Consent*\n\n"
                "Before we begin, please note:\n"
                "• ReminDAM is a reminder tool, NOT a medical service or healthcare provider.\n"
                "• We do NOT provide medical advice or recommend dosages.\n"
                "• You are responsible for verifying all info with a licensed professional.\n\n"
                "By clicking Agree, you consent to the processing of your data (including health-related info) per our Privacy Policy.\n\n"
                "Full Disclaimer: " + f"{settings.BASE_URL}/legal/disclaimer.html\n"
                "Terms: " + f"{settings.BASE_URL}/legal/terms.html\n"
                "Privacy: " + f"{settings.BASE_URL}/legal/privacy.html"
            ),
            buttons=[
                Button(id="terms_agree", text="✅ I Agree"),
                Button(id="terms_decline", text="❌ I Decline"),
            ],
            content_sid=settings.CT_TERMS_CONDITIONS,
            content_variables={"1": settings.BASE_URL},
        )
        await whatsapp_service.send(whatsapp_number, tc_msg, db=db, user_id=new_user.id)

        # Set state to await T&C acceptance
        try:
            state_svc = _get_state_service()
            await state_svc.set_state(whatsapp_number, "terms_accept", {})
        except Exception:
            logger.warning("Redis unavailable, T&C state not saved")


intent_service = IntentService()
