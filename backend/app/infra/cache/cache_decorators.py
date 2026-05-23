"""Cache decorators — @cache_result and @invalidate_cache."""

import functools
import json
from typing import Any

from app.core.logging import get_logger
from app.infra.cache.cache_service import delete_cache, get_cache, invalidate_pattern, set_cache

logger = get_logger(__name__)


def cache_result(prefix: str, ttl: int = 3600):
    """Decorator that caches the return value of an async function.

    Cache key format: app:{prefix}:{arg0_id}

    Usage:
        @cache_result(prefix="resume:summary", ttl=3600)
        async def parse_resume(self, resume_id: UUID) -> dict: ...
    """

    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            # Build cache key from prefix + first positional arg (usually an ID)
            identifier = str(args[1]) if len(args) > 1 else str(args[0])
            key = f"app:{prefix}:{identifier}"

            cached = await get_cache(key)
            if cached is not None:
                logger.info(f"Cache HIT {key}")
                return cached

            result = await fn(*args, **kwargs)
            await set_cache(key, result, ttl=ttl)
            return result

        return wrapper

    return decorator


def invalidate_cache(pattern: str):
    """Decorator that invalidates cache matching a pattern after the function runs.

    Usage:
        @invalidate_cache(pattern="app:resume:summary:*")
        async def update_resume(self, resume_id: UUID, data: dict) -> dict: ...
    """

    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            result = await fn(*args, **kwargs)
            deleted = await invalidate_pattern(pattern)
            if deleted:
                logger.info(f"Cache invalidated {deleted} keys matching {pattern}")
            return result

        return wrapper

    return decorator
