"""A short-lived cache of API response bodies in Redis, shared by every gunicorn worker, that fails open.

Used by /api/series: many visitors opening the dashboard ask for the same chart range within a minute or two,
and each answer is one aggregate query over the whole range. With the cache, the first request runs it and the
others get the stored bytes until the entry expires.

Off unless API_CACHE_REDIS_URL is set (docker-compose.yml sets it for the backend; tests leave it unset). If
Redis is down or slow, requests go straight to the database: a failed call is logged, and that worker doesn't
try Redis again for RETRY_AFTER_S, so an outage costs one short timeout per worker every 30 s, not one per
request.
"""
import logging
import threading
import time

import redis

from config import Config

log = logging.getLogger(__name__)

RETRY_AFTER_S = 30
MAX_BYTES = 5 * 1024 * 1024  # bodies bigger than this aren't stored: Redis also holds the export queue

_lock = threading.Lock()
_client = None
_down_until = 0.0


def _get_client():
    global _client
    if not Config.API_CACHE_REDIS_URL or time.monotonic() < _down_until:
        return None
    with _lock:
        if _client is None:
            # Short timeouts: a cache that makes requests wait is worse than none.
            _client = redis.Redis.from_url(Config.API_CACHE_REDIS_URL, socket_connect_timeout=0.2,
                                           socket_timeout=0.3)
        return _client


def _failed(action, exc):
    global _down_until
    _down_until = time.monotonic() + RETRY_AFTER_S
    log.warning("response cache %s failed (%s); not using it for %d s", action, type(exc).__name__, RETRY_AFTER_S)


def get(key):
    """(stored bytes, whole seconds until they expire) for `key`, or None (not stored, expired, cache off or
    unreachable)."""
    client = _get_client()
    if client is None:
        return None
    try:
        body, seconds_left = client.pipeline(transaction=False).get(key).ttl(key).execute()
    except (redis.RedisError, OSError) as exc:
        _failed("read", exc)
        return None
    if body is None or seconds_left is None or seconds_left < 0:  # gone, or (never here) stored without a TTL
        return None
    return body, seconds_left


def put(key, body, ttl_seconds):
    """Store `body` (bytes) under `key` for `ttl_seconds`; does nothing when the cache is off or unreachable."""
    if len(body) > MAX_BYTES:
        return
    client = _get_client()
    if client is None:
        return
    try:
        client.set(key, body, ex=ttl_seconds)
    except (redis.RedisError, OSError) as exc:
        _failed("write", exc)
