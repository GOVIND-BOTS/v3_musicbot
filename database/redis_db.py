import logging
from redis.asyncio import Redis
from config import REDIS_URL

LOGGER = logging.getLogger(__name__)

redis = None

async def connect_redis():
    global redis

    if not REDIS_URL:
        LOGGER.warning("REDIS_URL not set. Redis disabled.")
        return None

    try:
        redis = Redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
        )
        # Test connection
        await redis.ping()
        LOGGER.info("Redis connected successfully.")
        return redis
    except Exception as e:
        LOGGER.error(f"Redis connection failed: {e}")
        redis = None
        return None


async def close_redis():
    global redis
    if redis:
        try:
            await redis.close()
            LOGGER.info("Redis connection closed.")
        except Exception:
            pass
        redis = None


def get_redis():
    """Get current redis client (can be None if not connected)."""
    return redis
