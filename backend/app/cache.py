import os
import json
import logging
import functools
import inspect
from typing import Optional, Any, Callable
from redis.asyncio import Redis
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from app.logging_config import get_logger

logger = get_logger("sentinel.cache")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Setup connection
try:
    redis_client = Redis.from_url(REDIS_URL, decode_responses=True)
except Exception as e:
    logger.error(f"Failed to initialize Redis client at {REDIS_URL}: {e}")
    redis_client = None


async def get(key: str) -> Optional[str]:
    """Retrieve string value from cache."""
    if redis_client is None:
        return None
    try:
        return await redis_client.get(key)
    except Exception as e:
        logger.error(f"Redis GET error for key '{key}': {e}")
        return None


async def set(key: str, value: str, ttl_seconds: Optional[int] = None) -> bool:
    """Set value in cache with optional TTL."""
    if redis_client is None:
        return False
    try:
        await redis_client.set(key, value, ex=ttl_seconds)
        return True
    except Exception as e:
        logger.error(f"Redis SET error for key '{key}': {e}")
        return False


async def delete(key: str) -> bool:
    """Delete value from cache."""
    if redis_client is None:
        return False
    try:
        result = await redis_client.delete(key)
        return bool(result)
    except Exception as e:
        logger.error(f"Redis DELETE error for key '{key}': {e}")
        return False


def cached(ttl_seconds: int = 3600):
    """
    Decorator to cache the JSON-serialized return value of external API calls.
    Generates a unique cache key based on the function name and its arguments.
    Supports both async and sync decorated functions.
    """
    def decorator(func: Callable[..., Any]):
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Build string parts for arguments to generate a robust cache key
            args_str = ":".join(map(str, args))
            kwargs_str = ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = f"sentinel:cache:{func.__name__}:{args_str}:{kwargs_str}"

            # Attempt to retrieve from cache
            cached_val = await get(cache_key)
            if cached_val is not None:
                try:
                    return json.loads(cached_val)
                except Exception:
                    # Return raw string if JSON parsing fails
                    return cached_val

            # Call the target function (handling both sync and async functions)
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # Store the serialized result in the background
            try:
                serialized = json.dumps(result)
                await set(cache_key, serialized, ttl_seconds)
            except Exception as e:
                logger.warning(f"Failed to cache result for function '{func.__name__}': {e}")

            return result
        return wrapper
    return decorator
