import logging
from unittest.mock import MagicMock, patch

import pytest

from app.services.whatsapp_service import WhatsAppService

# These tests simulate both mocked mode and real mode


@pytest.mark.asyncio
async def test_whatsapp_service_mock_mode(caplog):
    """Test the service when Twilio credentials are not provided."""
    with patch("app.services.whatsapp_service.settings") as mock_settings:
        mock_settings.TWILIO_ACCOUNT_SID = None
        mock_settings.TWILIO_AUTH_TOKEN = None

        service = WhatsAppService()
        assert service.client is None

        with caplog.at_level(logging.INFO):
            result = await service.send_message("+2348000000000", "Mock Test")

            assert result is not None
            assert result.startswith("MOCK_")
            assert (
                "[MOCK WHATSAPP] To: whatsapp:+2348000000000 | Message: Mock Test"
                in caplog.text
            )


@pytest.mark.asyncio
async def test_whatsapp_service_real_mode_success():
    """Test the service when Twilio credentials are provided and the call succeeds."""
    with patch("app.services.whatsapp_service.settings") as mock_settings:
        mock_settings.TWILIO_ACCOUNT_SID = "fake_sid"
        mock_settings.TWILIO_AUTH_TOKEN = "fake_token"
        mock_settings.TWILIO_WHATSAPP_NUMBER = "12345"

        with patch("app.services.whatsapp_service.Client") as mock_client_class:
            mock_client_instance = MagicMock()
            mock_client_class.return_value = mock_client_instance

            # Setup the mocked response
            mock_msg = MagicMock()
            mock_msg.sid = "SM123"
            mock_client_instance.messages.create.return_value = mock_msg

            service = WhatsAppService()
            assert service.client is not None

            result = await service.send_message("+2348000000000", "Real Test")

            assert result == "SM123"
            mock_client_instance.messages.create.assert_called_once_with(
                body="Real Test", from_="whatsapp:12345", to="whatsapp:+2348000000000"
            )


@pytest.mark.asyncio
async def test_whatsapp_service_real_mode_failure(caplog):
    """Test the service when Twilio API call raises an exception."""
    with patch("app.services.whatsapp_service.settings") as mock_settings:
        mock_settings.TWILIO_ACCOUNT_SID = "fake_sid"
        mock_settings.TWILIO_AUTH_TOKEN = "fake_token"
        mock_settings.TWILIO_WHATSAPP_NUMBER = "12345"

        with patch("app.services.whatsapp_service.Client") as mock_client_class:
            mock_client_instance = MagicMock()
            mock_client_class.return_value = mock_client_instance

            # Setup the mocked exception
            mock_client_instance.messages.create.side_effect = Exception("Twilio Error")

            service = WhatsAppService()

            with caplog.at_level(logging.ERROR):
                result = await service.send_message("+2348000000000", "Fail Test")

                assert result is None
                assert "Failed to send WhatsApp message" in caplog.text
                assert "Twilio Error" in caplog.text
