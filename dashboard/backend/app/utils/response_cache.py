"""A short-lived cache of API response bodies in Redis, shared by every gunicorn worker, that fails open.

Used by /api/series and /api/windrose: many visitors opening the dashboard ask for the same chart range within a
minute or two, and each answer is one aggregate query over the whole range. With the cache, the first request runs it
and the others get the stored bytes until the entry expires. /api/series stores each series' part of each tile on its
own and reads or writes a request's entries in one round trip (get_many, put_many).

Off unless API_CACHE_REDIS_URL is set (docker-compose.yml sets it for the backend; tests leave it unset). If
Redis is down or slow, requests go straight to the database: a failed call is logged, and that worker doesn't
try Redis again for RETRY_AFTER_S, so an outage costs one short timeout per worker every 30 s, not one per
request.
"""
import logging
import threading
import time

import redis
from redis.backoff import NoBackoff
from redis.retry import Retry

from config import Config

log = logging.getLogger(__name__)

RETRY_AFTER_S = 30
# Bodies bigger than this aren't stored: Redis also holds the export queue. A wind rose answer is a few kilobytes, and
# so is one series' part of one /api/series tile (360 buckets).
MAX_BYTES = 3 * 1024 * 1024

_lock = threading.Lock()
_client = None
_down_until = 0.0


def _get_client():
    global _client
    if not Config.API_CACHE_REDIS_URL or time.monotonic() < _down_until:
        return None
    with _lock:
        if _client is None:
            # Short timeouts and no retries (redis-py retries 3 times by default in 7.x, 10 with backoff in
            # 8.x): a cache that makes requests wait is worse than none.
            _client = redis.Redis.from_url(Config.API_CACHE_REDIS_URL, socket_connect_timeout=0.2,
                                           socket_timeout=0.3, retry=Retry(NoBackoff(), 0), retry_on_error=[])
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


def get_many(keys):
    """{key: (stored bytes, whole seconds until they expire)} for those of `keys` that are stored, read in one round
    trip; {} when the cache is off or unreachable."""
    client = _get_client()
    if client is None or not keys:
        return {}
    try:
        pipe = client.pipeline(transaction=False)
        for key in keys:
            pipe.get(key).ttl(key)
        replies = pipe.execute()
    except (redis.RedisError, OSError) as exc:
        _failed("read", exc)
        return {}
    found = {}
    for key, body, seconds_left in zip(keys, replies[0::2], replies[1::2]):
        if body is not None and seconds_left is not None and seconds_left >= 0:
            found[key] = (body, seconds_left)
    return found


def put_many(items):
    """Store each (key, body, ttl_seconds) of `items` in one round trip, as put() does one."""
    items = [(key, body, ttl) for key, body, ttl in items if len(body) <= MAX_BYTES]
    client = _get_client()
    if client is None or not items:
        return
    try:
        pipe = client.pipeline(transaction=False)
        for key, body, ttl in items:
            pipe.set(key, body, ex=ttl)
        pipe.execute()
    except (redis.RedisError, OSError) as exc:
        _failed("write", exc)
