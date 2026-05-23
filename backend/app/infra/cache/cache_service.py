"""Cache service — high-level cache operations with TTL strategies."""

import json
from collections.abc import Callable
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.infra.cache.redis_client import redis_client

logger = get_logger(__name__)

# ── TTL Strategy ──────────────────────────────────────────────────────
# Summary results: 1h
# Question results: 30min
# Explanation results: 2h
# Task status: 10min

TTL_SUMMARY = 1200
TTL_QUESTION = 600
TTL_EXPLAIN = 1200
TTL_TASK_STATUS = 180
CACHE_MAX_INLINE_CHARS = 3000


def _make_key(prefix: str, identifier: str) -> str:
    """Build a cache key following the naming convention: app:{module}:{action}:{identifier}"""
    return f"app:{prefix}:{identifier}"


async def get_cache(key: str) -> Any | None:
    """Get a cached value. Returns None on miss or Redis unavailable."""
    raw = await redis_client.get(key)
    if raw is not None:
        logger.debug(f"Cache HIT: {key}")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    logger.debug(f"Cache MISS: {key}")
    return None


async def set_cache(key: str, value: Any, ttl: int = settings.REDIS_CACHE_TTL) -> bool:
    """Store a value in cache with TTL.

    Large payloads are truncated to keep local Redis memory within a safe range.
    """
    if isinstance(value, (dict, list)):
        serialized = json.dumps(value, ensure_ascii=False)
    else:
        serialized = str(value)

    if len(serialized) > CACHE_MAX_INLINE_CHARS:
        logger.warning(
            f"Cache value too large for key={key}; skipping cache write (size={len(serialized)} > {CACHE_MAX_INLINE_CHARS})"
        )
        return False

    return await redis_client.set(key, serialized, ttl=ttl)


async def delete_cache(key: str) -> bool:
    """Delete a cache key."""
    return await redis_client.delete(key)


async def invalidate_pattern(pattern: str) -> int:
    """Delete all keys matching a glob pattern."""
    return await redis_client.delete_pattern(pattern)


async def get_or_set(
    key: str,
    factory_fn: Callable,
    ttl: int = settings.REDIS_CACHE_TTL,
) -> Any:
    """Cache-aside pattern: return cached value or call factory and cache result."""
    cached = await get_cache(key)
    if cached is not None:
        return cached
    result = await factory_fn()
    await set_cache(key, result, ttl=ttl)
    return result
