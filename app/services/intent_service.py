import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.flow_service import flow_service
from app.services.message_types import TextMsg
from app.services.user_service import user_service
from app.services.whatsapp_service import whatsapp_service

logger = logging.getLogger(__name__)


def _get_state_service():
    from app.services.state_service import state_service

    return state_service


class IntentService:
    """Routes incoming WhatsApp messages through the flow engine."""

    async def handle_message(
        self,
        db: AsyncSession,
        whatsapp_number: str,
        message_body: str,
    ) -> None:
        """Process incoming message and send the response."""
        user = await user_service.get_by_whatsapp_number(db, whatsapp_number)

        if not user:
            deleted_user = await user_service.get_by_whatsapp_number(
                db, whatsapp_number, include_deleted=True
            )

            if deleted_user and deleted_user.deleted_at is not None:
                await self._handle_deleted_user(
                    db, whatsapp_number, message_body, deleted_user
                )
            else:
                await self._handle_new_user(db, whatsapp_number)
            return

        try:
            state_svc = _get_state_service()
            state_info = await state_svc.get_state(whatsapp_number)
        except Exception:
            logger.warning("Redis unavailable, defaulting to idle")
            state_info = {"state": "idle", "data": {}}

        state = state_info.get("state", "idle")
        data = state_info.get("data", {})

        body = message_body.strip()

        if body in ("take_action", "snooze_action", "skip_action"):
            last_reminder_id = data.get("_last_reminder_id")
            if last_reminder_id:
                action_type = body.split("_")[0]  # 'take', 'snooze', 'skip'
                body = f"{action_type}_{last_reminder_id}"

        response_msg, next_state, state_data = await flow_service.handle(
            db, user, state, data, body
        )

        await whatsapp_service.send(
            whatsapp_number,
            response_msg,
            db=db,
            user_id=user.id,
        )

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

    async def _handle_deleted_user(
        self,
        db: AsyncSession,
        whatsapp_number: str,
        message_body: str,
        deleted_user,
    ) -> None:
        """Handle messages from a soft-deleted user within their 90-day window."""
        body = message_body.strip().upper()

        if body == "RESTORE":
            restored = await user_service.restore_account(db, deleted_user.id)
            if restored:
                msg = TextMsg(
                    body=(
                        "✅ Welcome back! Your account has been reactivated.\n\n"
                        "All your previous data has been restored. "
                        "Send any message to continue."
                    )
                )
            else:
                msg = TextMsg(
                    body=(
                        "❌ Sorry, your account has already been permanently deleted "
                        "and cannot be restored.\n\n"
                        "Reply SIGNUP to create a new account."
                    )
                )
            await whatsapp_service.send(
                whatsapp_number, msg, db=db, user_id=deleted_user.id
            )
            return

        msg = TextMsg(
            body=(
                "❌ This number is no longer registered.\n\n"
                "Reply *RESTORE* to reactivate your account, "
                "or *SIGNUP* to create a new one."
            )
        )
        await whatsapp_service.send(
            whatsapp_number, msg, db=db, user_id=deleted_user.id
        )

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

        tc_msg = ButtonMsg(
            body=(
                "⚖️ *Medical Disclaimer & Consent*\n\n"
                "Before we begin, please note:\n"
                "• RemindAm is a reminder tool, NOT a medical service "
                "or healthcare provider.\n"
                "• We do NOT provide medical advice or recommend dosages.\n"
                "• You are responsible for verifying all info with a "
                "licensed professional.\n\n"
                "By clicking Agree, you consent to the processing of your data "
                "(including health-related info) per our Privacy Policy.\n\n"
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

        try:
            state_svc = _get_state_service()
            await state_svc.set_state(whatsapp_number, "terms_accept", {})
        except Exception:
            logger.warning("Redis unavailable, T&C state not saved")


intent_service = IntentService()
