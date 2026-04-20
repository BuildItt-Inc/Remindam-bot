import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.payment import process_successful_payment, verify_paystack_webhook

router = APIRouter(prefix="/payments", tags=["payments"])
logger = logging.getLogger(__name__)


@router.post("/webhook")
async def paystack_webhook(
    request: Request,
    x_paystack_signature: str = Header(...),
    db: AsyncSession = Depends(get_db),
):
    """Paystack Payment Webhook."""
    payload = await request.body()

    # 1. Verify signature
    if not verify_paystack_webhook(payload, x_paystack_signature):
        logger.warning("Invalid Paystack webhook signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )

    # 2. Parse event from raw bytes (avoid double-read)
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    event = data.get("event")

    if event == "charge.success":
        reference = data["data"]["reference"]
        success = await process_successful_payment(db, reference)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment reference not found",
            )

    return Response(status_code=status.HTTP_200_OK)


import html

from fastapi.responses import HTMLResponse


@router.get("/callback", response_class=HTMLResponse)
async def paystack_callback(
    reference: str,
):
    """Browser redirect after Paystack payment attempt."""
    safe_ref = html.escape(reference)
    html_content = f"""
    <html>
        <head>
            <title>Payment Status</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: sans-serif; text-align: center; padding: 50px; background-color: #f9f9f9; }}
                .box {{ border: 1px solid #e0e0e0; border-radius: 10px; padding: 30px; max-width: 400px; margin: 0 auto; background-color: white; box-shadow: 0 4px 8px rgba(0,0,0,0.05); }}
                h1 {{ color: #28a745; margin-bottom: 10px; }}
                p {{ color: #555; line-height: 1.5; }}
            </style>
        </head>
        <body>
            <div class="box">
                <h1>Payment Processing</h1>
                <p>Your payment (Ref: <strong>{safe_ref}</strong>) is being processed.</p>
                <p>Please close this window and return to WhatsApp. You will receive a confirmation message shortly!</p>
            </div>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)
