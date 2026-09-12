"""
Single shared Redis connection used for anything that isn't a Celery
broker message -- currently just short-lived OAuth state tokens. Celery
itself manages its own Redis connections separately (see core/celery_app.py).
"""
from functools import lru_cache

import redis

from app.core.config import settings


@lru_cache
def get_redis() -> redis.Redis:
    return redis.from_url(settings.REDIS_URL, decode_responses=True)
