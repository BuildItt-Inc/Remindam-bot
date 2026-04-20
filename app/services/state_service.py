import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)


class StateService:
    """Redis-backed conversational state management.

    Uses lazy initialization so the app doesn't crash if Redis
    is unavailable at import time.
    """

    def __init__(self):
        self._redis = None
        self.default_expiry = 3600  # 1 hour

    @property
    def redis(self):
        """Lazily create the Redis connection on first use."""
        if self._redis is None:
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis

    async def set_state(
        self,
        whatsapp_number: str,
        state: str,
        data: dict | None = None,
    ):
        """Set the conversational state and data for a user."""
        key = f"state:{whatsapp_number}"
        value = {"state": state, "data": data or {}}
        await self.redis.set(key, json.dumps(value), ex=self.default_expiry)

    async def get_state(self, whatsapp_number: str) -> dict:
        """Get the current state and data for a user."""
        key = f"state:{whatsapp_number}"
        value = await self.redis.get(key)
        if value:
            return json.loads(value)
        return {"state": "idle", "data": {}}

    async def clear_state(self, whatsapp_number: str):
        """Clear the conversational state for a user."""
        key = f"state:{whatsapp_number}"
        await self.redis.delete(key)

    async def update_data(
        self,
        whatsapp_number: str,
        data_key: str,
        data_value: Any,
    ):
        """Update a specific data field without changing the state."""
        state_info = await self.get_state(whatsapp_number)
        state_info["data"][data_key] = data_value
        await self.set_state(
            whatsapp_number,
            state_info["state"],
            state_info["data"],
        )


state_service = StateService()
