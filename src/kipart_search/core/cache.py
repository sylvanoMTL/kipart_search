"""SQLite cache with per-source TTL."""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from pathlib import Path

log = logging.getLogger(__name__)

# Default TTL values in seconds
TTL_PRICING = 4 * 3600       # 4 hours
TTL_PARAMETRIC = 7 * 86400   # 7 days
TTL_DATASHEET = 0            # Indefinite (0 = no expiry)


class QueryCache:
    """SQLite-backed cache for API/search results.

    Inspired by KiCost's QueryCache pattern but using SQLite.
    Cache keys: {source}:{query_type}:{sha256(normalized_query)}
    """

    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            from kipart_search.core.paths import cache_path
            db_path = cache_path()
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path), check_same_thread=False,
            )
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    source TEXT NOT NULL,
                    query_type TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    ttl REAL NOT NULL
                )
            """)
        return self._conn

    @staticmethod
    def _make_key(source: str, query_type: str, query: str) -> str:
        normalized = f"{source}:{query_type}:{query}".lower()
        return hashlib.sha256(normalized.encode()).hexdigest()

    def get(self, source: str, query_type: str, query: str) -> dict | list | None:
        """Retrieve a cached result, or None if expired/missing."""
        conn = self._get_conn()
        key = self._make_key(source, query_type, query)
        row = conn.execute(
            "SELECT value, created_at, ttl FROM cache WHERE key = ?", (key,)
        ).fetchone()

        if row is None:
            return None

        value, created_at, ttl = row
        if ttl > 0 and (time.time() - created_at) > ttl:
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            conn.commit()
            return None

        return json.loads(value)

    def put(
        self, source: str, query_type: str, query: str,
        value: dict | list, ttl: float = TTL_PARAMETRIC,
    ) -> None:
        """Store a result in cache."""
        conn = self._get_conn()
        key = self._make_key(source, query_type, query)
        conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, source, query_type, created_at, ttl) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (key, json.dumps(value), source, query_type, time.time(), ttl),
        )
        conn.commit()

    def invalidate(self, source: str | None = None) -> int:
        """Delete cache entries. If source is given, only that source; otherwise all."""
        conn = self._get_conn()
        if source is None:
            cursor = conn.execute("DELETE FROM cache")
        else:
            cursor = conn.execute("DELETE FROM cache WHERE source = ?", (source,))
        conn.commit()
        return cursor.rowcount

    def is_expired(self, source: str, query_type: str, query: str) -> bool:
        """Check if a cache entry is expired (or missing)."""
        conn = self._get_conn()
        key = self._make_key(source, query_type, query)
        row = conn.execute(
            "SELECT created_at, ttl FROM cache WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return True
        created_at, ttl = row
        if ttl == 0:
            return False
        return (time.time() - created_at) > ttl

    def stats(self) -> dict:
        """Return cache statistics: entry count, total size, oldest entry."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(LENGTH(value)), 0), MIN(created_at) FROM cache"
        ).fetchone()
        return {
            "count": row[0],
            "total_size_bytes": row[1],
            "oldest_created_at": row[2],
        }

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
