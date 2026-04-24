import json
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.message import MessageLog
from app.services.message_types import Msg

logger = logging.getLogger(__name__)


def mask_phone_number(number: str) -> str:
    """Mask a phone number for safe logging (e.g., +234****6789)."""
    if not number:
        return "UNKNOWN"
    if len(number) <= 8:
        return "****"
    return f"{number[:4]}****{number[-4:]}"


class WhatsAppService:
    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.from_number = settings.TWILIO_WHATSAPP_NUMBER
        self.messaging_service_sid = settings.TWILIO_MESSAGING_SERVICE_SID
        self.mock_mode = not self.account_sid or not self.auth_token

        if self.mock_mode:
            logger.warning(
                "Twilio credentials not set. WhatsAppService running in mock mode."
            )

    def _get_client(self):
        """Lazily create Twilio client to avoid import errors in tests."""
        from twilio.rest import Client

        return Client(self.account_sid, self.auth_token)

    # ── Public API ──

    async def send(
        self,
        to_number: str,
        msg: Msg,
        *,
        db: AsyncSession | None = None,
        user_id: UUID | None = None,
        reminder_log_id: UUID | None = None,
        commit: bool = True,
    ) -> str | None:
        """Send a structured message.

        If the message has a content_sid, sends via Twilio Content API
        (native buttons/lists). Otherwise sends as plain text.

        Returns the Twilio message SID (or mock ID).
        """
        content_sid = getattr(msg, "content_sid", "")
        content_variables = getattr(msg, "content_variables", {})

        if content_sid:
            return await self._send_template(
                to_number,
                content_sid,
                content_variables,
                db=db,
                user_id=user_id,
                reminder_log_id=reminder_log_id,
                commit=commit,
            )

        text = msg.body
        return await self._send_text(
            to_number,
            text,
            db=db,
            user_id=user_id,
            reminder_log_id=reminder_log_id,
            commit=commit,
        )

    async def _send_template(
        self,
        to_number: str,
        content_sid: str,
        content_variables: dict,
        *,
        db: AsyncSession | None = None,
        user_id: UUID | None = None,
        reminder_log_id: UUID | None = None,
        commit: bool = True,
    ) -> str | None:
        """Send a message using a Twilio Content Template (native buttons/lists)."""
        msg_id = None
        status = "failed"

        if not self.mock_mode:
            try:
                client = self._get_client()
                kwargs = {
                    "content_sid": content_sid,
                    "to": f"whatsapp:{to_number}",
                }

                if content_variables:
                    kwargs["content_variables"] = json.dumps(content_variables)

                if self.messaging_service_sid:
                    kwargs["messaging_service_sid"] = self.messaging_service_sid
                else:
                    kwargs["from_"] = f"whatsapp:{self.from_number}"

                twilio_msg = client.messages.create(**kwargs)
                msg_id = twilio_msg.sid
                status = "sent"
                logger.info(
                    "Sent WhatsApp template to %s, sid: %s",
                    mask_phone_number(to_number),
                    msg_id,
                )
            except Exception as e:
                logger.error(
                    "Failed to send WhatsApp template to %s: %s",
                    mask_phone_number(to_number),
                    e,
                )
        else:
            msg_id = f"MOCK_{UUID(int=0)}"
            status = "sent"
            logger.info(
                "[MOCK WHATSAPP] To: %s | Template: %s | Vars: %s",
                mask_phone_number(to_number),
                content_sid,
                content_variables,
            )

        await self._log(db, user_id, reminder_log_id, msg_id, status, commit=commit)
        return msg_id

    async def _send_text(
        self,
        to_number: str,
        message: str,
        *,
        media_url: str | None = None,
        db: AsyncSession | None = None,
        user_id: UUID | None = None,
        reminder_log_id: UUID | None = None,
        commit: bool = True,
    ) -> str | None:
        """Send a plain text message (or media) via Twilio."""
        msg_id = None
        status = "failed"

        if not self.mock_mode:
            try:
                client = self._get_client()
                kwargs = {
                    "body": message,
                    "from_": f"whatsapp:{self.from_number}",
                    "to": f"whatsapp:{to_number}",
                }
                if media_url:
                    kwargs["media_url"] = [media_url]

                twilio_msg = client.messages.create(**kwargs)
                msg_id = twilio_msg.sid
                status = "sent"
                masked_to = mask_phone_number(to_number)
                logger.info("Sent WhatsApp text to %s, sid: %s", masked_to, msg_id)
            except Exception as e:
                logger.error(
                    "Failed to send WhatsApp message to %s: %s",
                    mask_phone_number(to_number),
                    e,
                )
        else:
            msg_id = f"MOCK_{UUID(int=0)}"
            status = "sent"
            logger.info(
                "[MOCK WHATSAPP] To: %s | Message: %s",
                mask_phone_number(to_number),
                message[:80],
            )

        await self._log(db, user_id, reminder_log_id, msg_id, status, commit=commit)
        return msg_id

    # ── Helpers ──

    async def _log(
        self,
        db: AsyncSession | None,
        user_id: UUID | None,
        reminder_log_id: UUID | None,
        msg_id: str | None,
        status: str,
        commit: bool = True,
    ):
        """Store message metadata (no content) for delivery tracking."""
        if db and user_id:
            try:
                log_entry = MessageLog(
                    user_id=user_id,
                    reminder_log_id=reminder_log_id,
                    provider_message_id=msg_id,
                    status=status,
                    direction="outbound",
                )
                db.add(log_entry)
                if commit:
                    await db.commit()
            except Exception as e:
                logger.error("Failed to log message to DB: %s", e)


whatsapp_service = WhatsAppService()
