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


@router.post(
    "/webhook",
    summary="Twilio WhatsApp Webhook",
    description=(
        "Main entrypoint for all WhatsApp incoming traffic. "
        "Twilio posts x-www-form-urlencoded payloads containing "
        "user messages and interactive button responses."
    ),
)
@limiter.limit("5/minute")
async def twilio_webhook(
    request: Request,
    x_twilio_signature: str = Header(
        ...,
        alias="X-Twilio-Signature",
        description="Cryptographic Twilio signature required to prevent spoofing",
    ),
    db: AsyncSession = Depends(get_db),
):
    """Process an incoming WhatsApp message from Twilio and return empty TwiML.

    Validates the Twilio signature before any processing.
    Extracts message body with priority: ButtonPayload > ListId > Body.
    Delegates to the intent engine and always returns 200 OK to Twilio.
    """
    form_data = await request.form()

    if not settings.TWILIO_AUTH_TOKEN:
        logger.critical("TWILIO_AUTH_TOKEN is not set. Rejecting webhook request!")
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    # Use BASE_URL so signature validation is not affected by reverse-proxy headers.
    url = f"{settings.BASE_URL}{request.url.path}"
    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)

    post_vars = {}
    for k, v in form_data.multi_items():
        if k in post_vars:
            if not isinstance(post_vars[k], list):
                post_vars[k] = [post_vars[k]]
            post_vars[k].append(v)
        else:
            post_vars[k] = v

    if not validator.validate(url, post_vars, x_twilio_signature):
        logger.warning("Invalid Twilio signature for URL: %s", url)
        return Response(status_code=status.HTTP_403_FORBIDDEN)

    from_number = form_data.get("From", "")
    phone = from_number.replace("whatsapp:", "")

    button_payload = form_data.get("ButtonPayload", "")
    list_id = form_data.get("ListId", "")
    body = form_data.get("Body", "")

    # Priority: ButtonPayload > ListId > plain Body
    message_body = (button_payload or list_id or body).strip()

    if not phone or not message_body:
        return Response(
            content=EMPTY_TWIML,
            media_type="application/xml",
            status_code=status.HTTP_200_OK,
        )

    # Log message type without logging raw user content or full phone numbers.
    msg_type = "button" if button_payload else ("list" if list_id else "text")
    logger.info(
        "Incoming WhatsApp msg_type=%s phone_suffix=...%s", msg_type, phone[-4:]
    )

    await intent_service.handle_message(db, phone, message_body)

    return Response(
        content=EMPTY_TWIML,
        media_type="application/xml",
        status_code=status.HTTP_200_OK,
    )
