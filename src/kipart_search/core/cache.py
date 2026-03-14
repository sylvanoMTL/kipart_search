"""SQLite cache with per-source TTL."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path


# Default TTL values in seconds
TTL_PRICING = 4 * 3600       # 4 hours
TTL_PARAMETRIC = 7 * 86400   # 7 days
TTL_DATASHEET = 0            # Indefinite (0 = no expiry)


class QueryCache:
    """SQLite-backed cache for API/search results.

    Inspired by KiCost's QueryCache pattern but using SQLite.
    Cache keys: {source}:{query_type}:{normalized_query}
    """

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or Path.home() / ".kipart-search" / "cache.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
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

    def get(self, source: str, query_type: str, query: str) -> dict | None:
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
        self, source: str, query_type: str, query: str, value: dict, ttl: float = TTL_PARAMETRIC
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

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
