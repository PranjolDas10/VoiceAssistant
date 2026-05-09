"""SQLite-backed response cache with per-namespace TTLs and hit-rate tracking."""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Namespace TTLs (seconds)
_TTL: dict[str, int] = {
    "weather":   1800,   # 30 min  — conditions change slowly
    "news":       900,   # 15 min  — headlines rotate frequently
    "wikipedia": 86400,  # 24 hr   — facts rarely change
    "wolfram":   3600,   # 1 hr    — math answers are stable
    "translate": 86400,  # 24 hr   — translations are deterministic
    "default":   3600,
}


class ResponseCache:
    """Thread-safe SQLite cache. Evicts stale rows on startup and on demand."""

    def __init__(self, db_path: str = "aria_cache.db") -> None:
        self.db_path = db_path
        self._hits = 0
        self._misses = 0
        self._init_db()

    # ── internals ────────────────────────────────────────────────────────────

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    key      TEXT PRIMARY KEY,
                    value    TEXT NOT NULL,
                    expires  REAL NOT NULL,
                    created  REAL NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_exp ON cache(expires)")
            conn.execute("DELETE FROM cache WHERE expires <= ?", (time.time(),))

    @staticmethod
    def _key(ns: str, query: str) -> str:
        raw = f"{ns}:{query.lower().strip()}"
        return hashlib.sha256(raw.encode()).hexdigest()

    # ── public API ────────────────────────────────────────────────────────────

    def get(self, ns: str, query: str) -> Optional[Any]:
        key = self._key(ns, query)
        with self._conn() as conn:
            row = conn.execute(
                "SELECT value FROM cache WHERE key=? AND expires>?",
                (key, time.time()),
            ).fetchone()
        if row:
            self._hits += 1
            logger.debug("CACHE HIT  [%s] %.60s", ns, query)
            return json.loads(row[0])
        self._misses += 1
        logger.debug("CACHE MISS [%s] %.60s", ns, query)
        return None

    def set(self, ns: str, query: str, value: Any, ttl: Optional[int] = None) -> None:
        ttl = ttl or _TTL.get(ns, _TTL["default"])
        key = self._key(ns, query)
        now = time.time()
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache VALUES (?,?,?,?)",
                (key, json.dumps(value), now + ttl, now),
            )

    def evict(self) -> int:
        """Remove all expired entries and return count deleted."""
        with self._conn() as conn:
            return conn.execute(
                "DELETE FROM cache WHERE expires<=?", (time.time(),)
            ).rowcount

    # ── metrics ───────────────────────────────────────────────────────────────

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total else 0.0

    def stats(self) -> dict:
        with self._conn() as conn:
            db_size = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{self.hit_rate:.1%}",
            "cached_entries": db_size,
            "total_requests": self._hits + self._misses,
        }
