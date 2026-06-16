from redis.asyncio import Redis

from app.config import get_settings


def get_redis_client() -> Redis:
    return Redis.from_url(
        get_settings().redis_url,
        decode_responses=True,
        socket_timeout=None,
    )
