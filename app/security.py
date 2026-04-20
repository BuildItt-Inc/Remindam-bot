import hmac

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
limiter = Limiter(key_func=get_remote_address)


def verify_api_key(api_key: str = Security(api_key_header)):
    """Enforce API Key validation for REST endpoints."""
    if not api_key or not hmac.compare_digest(api_key, settings.API_KEY):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Valid X-API-Key header is missing or incorrect",
        )
    return api_key
