"""
Cache abstraction layer.

Provides an async key/value cache with TTL support backed by an
in-memory dictionary. The public interface is designed so that a future
Redis-backed implementation can replace this class without any change
to callers (pipeline.py or any future batch).

Design constraints satisfied:
  - No external cache libraries
  - No Redis
  - Async interface throughout
  - TTL enforced lazily on read (no background eviction thread needed
    at this scale; eviction on write keeps memory bounded)
"""

from __future__ import annotations

import time
from typing import Any


class CacheService:
    """
    Async in-memory cache with per-entry TTL.

    All public methods are async so callers are written once and work
    unchanged when this class is replaced by a Redis-backed equivalent.

    Thread safety: this implementation is not thread-safe across OS
    threads, but is safe within a single-threaded asyncio event loop,
    which is the only execution context NovaMind currently uses.
    """

    def __init__(self, default_ttl_seconds: int = 300) -> None:
        self._default_ttl = default_ttl_seconds
        self._store: dict[str, tuple[Any, float]] = {}

    async def get(self, key: str) -> Any | None:
        """
        Returns the cached value for key, or None if the key does not
        exist or has expired. Expired entries are evicted on read.
        """
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int | None = None,
    ) -> None:
        """
        Stores value under key with an expiry of ttl_seconds from now.
        Uses default_ttl_seconds if ttl_seconds is not provided.
        Overwrites any existing entry for the same key.
        """
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        expires_at = time.monotonic() + ttl
        self._store[key] = (value, expires_at)

    async def delete(self, key: str) -> None:
        """Removes key from the cache. No-op if key does not exist."""
        self._store.pop(key, None)

    async def exists(self, key: str) -> bool:
        """Returns True if key exists and has not expired."""
        return await self.get(key) is not None

    async def clear(self) -> None:
        """Removes all entries from the cache."""
        self._store.clear()

    async def evict_expired(self) -> int:
        """
        Proactively removes all expired entries and returns the count
        removed. Optional — entries are also evicted lazily on get().
        Useful for periodic cleanup in long-running processes.
        """
        now = time.monotonic()
        expired_keys = [k for k, (_, exp) in self._store.items() if now > exp]
        for key in expired_keys:
            del self._store[key]
        return len(expired_keys)

    def size(self) -> int:
        """Returns the number of entries currently in the store,
        including any that may have expired but not yet been evicted."""
        return len(self._store)