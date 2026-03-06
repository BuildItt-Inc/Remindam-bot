import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from twilio.rest import Client

from app.config import settings
from app.models.message import MessageLog

logger = logging.getLogger(__name__)


class WhatsAppService:
    def __init__(self):
        # Initialize Twilio client only if configured
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            self.client = Client(
                settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN
            )
            self.from_number = f"whatsapp:{settings.TWILIO_WHATSAPP_NUMBER}"
        else:
            self.client = None
            logger.warning(
                "Twilio credentials not found. WhatsAppService will run in mock mode."
            )

    async def send_message(
        self,
        to_number: str,
        message: str,
        db: AsyncSession | None = None,
        user_id: UUID | None = None,
        reminder_log_id: UUID | None = None,
    ) -> str | None:
        """
        Send a WhatsApp message using Twilio and log the delivery metadata.
        If credentials are not set, it simply logs the message (mock mode).

        Returns the twilio_sid if successful, or a mock SID if in mock mode.
        """
        to_whatsapp = f"whatsapp:{to_number}"
        twilio_sid = None
        status = "failed"

        if self.client:
            try:
                msg = self.client.messages.create(
                    body=message, from_=self.from_number, to=to_whatsapp
                )
                twilio_sid = msg.sid
                status = "sent"
                logger.info(
                    f"Sent WhatsApp message to {to_whatsapp}, SID: {twilio_sid}"
                )
            except Exception as e:
                logger.error(f"Failed to send WhatsApp message to {to_whatsapp}: {e}")
        else:
            # Mock mode
            twilio_sid = f"MOCK_{UUID(int=0)}"
            status = "sent"
            logger.info(f"[MOCK WHATSAPP] To: {to_whatsapp} | Message: {message}")

        # Lite Logging: Store only metadata, no content for privacy
        if db and user_id:
            try:
                log_entry = MessageLog(
                    user_id=user_id,
                    reminder_log_id=reminder_log_id,
                    twilio_sid=twilio_sid,
                    status=status,
                    direction="outbound",
                )
                db.add(log_entry)
                await db.commit()
            except Exception as e:
                logger.error(f"Failed to log message to DB: {e}")

        return twilio_sid


whatsapp_service = WhatsAppService()
