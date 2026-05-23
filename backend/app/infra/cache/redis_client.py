"""Redis connection manager with graceful fallback."""

import logging
from typing import Any

import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(f"interview_practice.{__name__}")


class RedisClient:
    """Redis connection manager.

    Graceful fallback: if Redis is unavailable, all operations become no-ops.
    The `connected` property can be checked to know whether Redis is active.
    """

    def __init__(self) -> None:
        self._client: redis.Redis | None = None
        self._connected = False

    async def connect(self) -> None:
        if not settings.REDIS_ENABLED:
            logger.info("Redis is disabled (REDIS_ENABLED=False)")
            return
        try:
            self._client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=True,
            )
            await self._client.ping()
            self._connected = True
            logger.info(f"Redis connected: {settings.REDIS_URL}")
        except Exception:
            self._connected = False
            self._client = None
            logger.warning("Redis connection failed — running in no-cache mode")

    async def disconnect(self) -> None:
        if self._client:
            try:
                await self._client.close()
            except Exception:
                pass
            self._client = None
            self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected and self._client is not None

    @property
    def client(self) -> redis.Redis | None:
        return self._client

    async def get(self, key: str) -> str | None:
        if not self._connected or self._client is None:
            return None
        try:
            return await self._client.get(key)
        except Exception:
            logger.warning(f"Redis GET failed for key={key}")
            return None

    async def set(self, key: str, value: str, ttl: int | None = None) -> bool:
        if not self._connected or self._client is None:
            return False
        try:
            if ttl:
                await self._client.set(key, value, ex=ttl)
            else:
                await self._client.set(key, value)
            return True
        except Exception:
            logger.warning(f"Redis SET failed for key={key}")
            return False

    async def delete(self, key: str) -> bool:
        if not self._connected or self._client is None:
            return False
        try:
            await self._client.delete(key)
            return True
        except Exception:
            logger.warning(f"Redis DELETE failed for key={key}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        if not self._connected or self._client is None:
            return 0
        try:
            keys = await self._client.keys(pattern)
            if keys:
                return await self._client.delete(*keys)
            return 0
        except Exception:
            logger.warning(f"Redis DELETE pattern failed for pattern={pattern}")
            return 0


# Singleton
redis_client = RedisClient()
