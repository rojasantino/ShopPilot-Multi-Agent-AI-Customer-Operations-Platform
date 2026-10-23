"""Redis-backed cache + counters, with an in-memory fallback so the app still runs without Redis."""

import json
import logging
import time
from typing import Any

import redis

logger = logging.getLogger(__name__)


class Cache:
    def __init__(self, url: str | None) -> None:
        self._redis: redis.Redis | None = None
        self._local: dict[str, tuple[float, str]] = {}
        if url:
            try:
                client = redis.Redis.from_url(
                    url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1
                )
                client.ping()
                self._redis = client
            except redis.RedisError:
                logger.warning("Redis unreachable; falling back to in-memory cache")

    @property
    def backend(self) -> str:
        return "redis" if self._redis else "memory"

    def ping(self) -> bool:
        if not self._redis:
            return True
        try:
            return bool(self._redis.ping())
        except redis.RedisError:
            return False

    def get_json(self, key: str) -> Any | None:
        raw: str | None
        if self._redis:
            try:
                raw = self._redis.get(key)
            except redis.RedisError:
                return None
        else:
            entry = self._local.get(key)
            raw = entry[1] if entry and entry[0] > time.time() else None
        return json.loads(raw) if raw else None

    def set_json(self, key: str, value: Any, ttl: int) -> None:
        raw = json.dumps(value, default=str)
        if self._redis:
            try:
                self._redis.set(key, raw, ex=ttl)
            except redis.RedisError:
                logger.warning("cache write failed for %s", key)
        else:
            self._local[key] = (time.time() + ttl, raw)

    def hit(self, key: str, window_seconds: int) -> int:
        """Increment a counter that expires after `window_seconds` (used for rate limiting)."""
        if self._redis:
            try:
                pipe = self._redis.pipeline()
                pipe.incr(key)
                pipe.expire(key, window_seconds, nx=True)
                return int(pipe.execute()[0])
            except redis.RedisError:
                return 0  # fail open: never block customers because Redis is down
        expiry, raw = self._local.get(key, (0.0, "0"))
        count = int(raw) + 1 if expiry > time.time() else 1
        self._local[key] = (
            expiry if expiry > time.time() else time.time() + window_seconds,
            str(count),
        )
        return count
