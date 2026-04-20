from app.services.message_types import TextMsg

"""Tests for the Twilio-based WhatsApp service."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from app.services.whatsapp_service import WhatsAppService


@pytest.mark.asyncio
async def test_whatsapp_service_mock_mode(caplog):
    """Test the service when Twilio credentials are not provided."""
    with patch("app.services.whatsapp_service.settings") as mock_settings:
        mock_settings.TWILIO_ACCOUNT_SID = ""
        mock_settings.TWILIO_AUTH_TOKEN = ""
        mock_settings.TWILIO_WHATSAPP_NUMBER = ""

        service = WhatsAppService()
        assert service.mock_mode is True

        with caplog.at_level(logging.INFO):
            result = await service.send("+2348000000000", TextMsg("Mock Test"))

            assert result is not None
            assert result.startswith("MOCK_")
            assert "[MOCK WHATSAPP]" in caplog.text


@pytest.mark.asyncio
async def test_whatsapp_service_real_mode_success():
    """Test the service when Twilio credentials are provided."""
    with patch("app.services.whatsapp_service.settings") as mock_settings:
        mock_settings.TWILIO_ACCOUNT_SID = "ACtest123"
        mock_settings.TWILIO_AUTH_TOKEN = "test-token"
        mock_settings.TWILIO_WHATSAPP_NUMBER = "+14155238886"

        service = WhatsAppService()
        assert service.mock_mode is False

        # Mock the Twilio client
        mock_msg = MagicMock()
        mock_msg.sid = "SM_TEST_123"
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg
        service._get_client = MagicMock(return_value=mock_client)

        result = await service.send("+2348000000000", TextMsg("Real Test"))

        assert result == "SM_TEST_123"
        mock_client.messages.create.assert_called_once_with(
            body="Real Test",
            from_="whatsapp:+14155238886",
            to="whatsapp:+2348000000000",
        )


@pytest.mark.asyncio
async def test_whatsapp_service_real_mode_failure(caplog):
    """Test the service when Twilio call raises an exception."""
    with patch("app.services.whatsapp_service.settings") as mock_settings:
        mock_settings.TWILIO_ACCOUNT_SID = "ACtest123"
        mock_settings.TWILIO_AUTH_TOKEN = "test-token"
        mock_settings.TWILIO_WHATSAPP_NUMBER = "+14155238886"

        service = WhatsAppService()

        # Mock the Twilio client to raise
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("Connection Error")
        service._get_client = MagicMock(return_value=mock_client)

        with caplog.at_level(logging.ERROR):
            result = await service.send("+2348000000000", TextMsg("Fail Test"))

            assert result is None
            assert "Failed to send WhatsApp message" in caplog.text
