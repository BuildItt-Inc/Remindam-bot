"""Twilio WhatsApp webhook.

Receives incoming messages from Twilio and routes them
to the intent/flow engine. Responses are sent back
via Twilio REST API — the webhook just returns empty TwiML.

Handles three types of user input from Content Templates:
- ButtonPayload: sent when user taps a Quick Reply button
- ListId: sent when user selects a List Picker item
- Body: plain text typed by the user (or fallback)
"""

import logging
from collections.abc import Mapping

from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from twilio.request_validator import RequestValidator

from app.config import settings
from app.database import get_db
from app.security import limiter
from app.services.intent_service import intent_service

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])
logger = logging.getLogger(__name__)

EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


@router.post("/webhook")
@limiter.limit("5/minute")
async def twilio_webhook(
    request: Request,
    x_twilio_signature: str = Header(..., alias="X-Twilio-Signature"),
    db: AsyncSession = Depends(get_db),
):
    """Twilio WhatsApp webhook endpoint with Cryptographic Signature Validation."""
    form_data = await request.form()

    # SECURITY: Reject if auth token is not configured
    if not settings.TWILIO_AUTH_TOKEN:
        logger.critical("TWILIO_AUTH_TOKEN is not set. Rejecting webhook request!")
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    # Use BASE_URL for signature validation instead of trusting proxy headers
    url = f"{settings.BASE_URL}{request.url.path}"

    # Twilio sends auth token config
    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)

    # Format the form data to standard dict for Twilio validator
    post_vars: Mapping[str, str] = {k: v for k, v in form_data.items()}

    # Validate Signature
    if not validator.validate(url, post_vars, x_twilio_signature):
        logger.warning("Invalid Twilio Signature! Attempted URL: %s", url)
        return Response(status_code=status.HTTP_403_FORBIDDEN)

    from_number = form_data.get("From", "")

    # Twilio sends "whatsapp:+234..." — strip the prefix
    phone = from_number.replace("whatsapp:", "")

    # Extract the user's actual input:
    # 1. ButtonPayload — sent when user taps a Quick Reply button (Content API)
    # 2. ListId — sent when user selects a List Picker item (Content API)
    # 3. Body — plain text typed by the user (always present)
    button_payload = form_data.get("ButtonPayload", "")
    list_id = form_data.get("ListId", "")
    body = form_data.get("Body", "")

    # Priority: ButtonPayload > ListId > Body
    message_body = (button_payload or list_id or body).strip()

    if not phone or not message_body:
        return Response(
            content=EMPTY_TWIML,
            media_type="application/xml",
            status_code=status.HTTP_200_OK,
        )

    logger.info(
        "Incoming WhatsApp from %s | payload=%s | list_id=%s | body=%s",
        phone,
        button_payload,
        list_id,
        body,
    )

    # Process through the flow engine
    await intent_service.handle_message(db, phone, message_body)

    return Response(
        content=EMPTY_TWIML,
        media_type="application/xml",
        status_code=status.HTTP_200_OK,
    )
