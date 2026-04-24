from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


def _mock_validator_always_true():
    """Create a mock RequestValidator that always returns True."""
    mock_validator = MagicMock()
    mock_validator.validate.return_value = True
    return mock_validator


def test_twilio_webhook_extracts_body_and_from():
    """Test that the Twilio webhook correctly parses Body and From fields."""
    from app.main import app

    mock_validator = _mock_validator_always_true()

    with (
        patch("app.routes.whatsapp.intent_service") as mock_intent,
        patch("app.routes.whatsapp.settings.TWILIO_AUTH_TOKEN", "test-token"),
        patch("app.routes.whatsapp.RequestValidator", return_value=mock_validator),
    ):
        mock_intent.handle_message = AsyncMock()

        client = TestClient(app)
        response = client.post(
            "/whatsapp/webhook",
            data={
                "Body": "Hello Bot",
                "From": "whatsapp:+2348000000000",
                "To": "whatsapp:+14155238886",
            },
            headers={"X-Twilio-Signature": "dummy"},
        )

        assert response.status_code == 200
        assert "Response" in response.text
        mock_intent.handle_message.assert_called_once()
        call_args = mock_intent.handle_message.call_args
        assert call_args[0][1] == "+2348000000000"
        assert call_args[0][2] == "Hello Bot"


def test_twilio_webhook_empty_body():
    """Test that empty messages return empty TwiML without processing."""
    from app.main import app

    mock_validator = _mock_validator_always_true()

    with (
        patch("app.routes.whatsapp.intent_service") as mock_intent,
        patch("app.routes.whatsapp.settings.TWILIO_AUTH_TOKEN", "test-token"),
        patch("app.routes.whatsapp.RequestValidator", return_value=mock_validator),
    ):
        mock_intent.handle_message = AsyncMock()

        client = TestClient(app)
        response = client.post(
            "/whatsapp/webhook",
            data={
                "Body": "",
                "From": "whatsapp:+2348000000000",
            },
            headers={"X-Twilio-Signature": "dummy"},
        )

        assert response.status_code == 200
        mock_intent.handle_message.assert_not_called()


def test_twilio_webhook_strips_whatsapp_prefix():
    """Test that 'whatsapp:' prefix is stripped from the From number."""
    from app.main import app

    mock_validator = _mock_validator_always_true()

    with (
        patch("app.routes.whatsapp.intent_service") as mock_intent,
        patch("app.routes.whatsapp.settings.TWILIO_AUTH_TOKEN", "test-token"),
        patch("app.routes.whatsapp.RequestValidator", return_value=mock_validator),
    ):
        mock_intent.handle_message = AsyncMock()

        client = TestClient(app)
        client.post(
            "/whatsapp/webhook",
            data={
                "Body": "Test",
                "From": "whatsapp:+2348081669529",
            },
            headers={"X-Twilio-Signature": "dummy"},
        )

        call_args = mock_intent.handle_message.call_args
        assert call_args[0][1] == "+2348081669529"


def test_twilio_webhook_rejects_without_auth_token():
    """Test that the webhook returns 503 when TWILIO_AUTH_TOKEN is not set."""
    from app.main import app

    with patch("app.routes.whatsapp.settings.TWILIO_AUTH_TOKEN", ""):
        client = TestClient(app)
        response = client.post(
            "/whatsapp/webhook",
            data={
                "Body": "Hello Bot",
                "From": "whatsapp:+2348000000000",
            },
            headers={"X-Twilio-Signature": "dummy"},
        )

        assert response.status_code == 503


def test_twilio_webhook_rejects_invalid_signature():
    """Test that the webhook returns 403 on invalid signature."""
    from app.main import app

    mock_validator = MagicMock()
    mock_validator.validate.return_value = False

    with (
        patch("app.routes.whatsapp.settings.TWILIO_AUTH_TOKEN", "test-token"),
        patch("app.routes.whatsapp.RequestValidator", return_value=mock_validator),
    ):
        client = TestClient(app)
        response = client.post(
            "/whatsapp/webhook",
            data={
                "Body": "Hello Bot",
                "From": "whatsapp:+2348000000000",
            },
            headers={"X-Twilio-Signature": "bad-signature"},
        )

        assert response.status_code == 403
