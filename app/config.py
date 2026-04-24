from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration via environment variables."""

    DATABASE_URL: str = Field(..., description="PostgreSQL connection string")
    TEST_DATABASE_URL: str | None = None
    USE_NULL_POOL: bool = False
    DEBUG: bool = False

    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET_KEY: str = Field(..., description="Secret key for JWT generation")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Twilio (WhatsApp)
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_NUMBER: str = ""
    TWILIO_MESSAGING_SERVICE_SID: str = ""

    # Twilio Content Template SIDs
    CT_REMINDER_MEDICATION: str = ""
    CT_REMINDER_EXERCISE: str = ""
    CT_REMINDER_WATER: str = ""
    CT_TERMS_CONDITIONS: str = ""
    CT_GO_MENU: str = ""
    CT_BACK_MENU: str = ""
    CT_CONFIRM_CANCEL: str = ""
    CT_PREMIUM_REQUIRED: str = ""
    CT_LIMIT_REACHED: str = ""
    CT_TRIAL_EXPIRED: str = ""
    CT_MAIN_MENU_FREE: str = ""
    CT_MAIN_MENU_STANDARD: str = ""
    CT_MAIN_MENU_PREMIUM: str = ""
    CT_MEDICATION_FORM: str = ""
    CT_EXERCISE_TYPE: str = ""
    CT_WATER_AMOUNT: str = ""
    CT_WATER_INTERVAL: str = ""
    CT_PROFILE_MENU: str = ""

    PAYSTACK_SECRET_KEY: str = ""

    API_KEY: str = Field(
        default="dev-secret-key", description="API key for internal REST endpoints"
    )

    TRIAL_DAYS: int = 1
    GRACE_DAYS: int = 2
    SUBSCRIPTION_AMOUNT_STANDARD_KOBO: int = 50000
    SUBSCRIPTION_AMOUNT_PREMIUM_KOBO: int = 120000
    BASE_URL: str = "https://yourdomain.com"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
