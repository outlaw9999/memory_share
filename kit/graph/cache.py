"""
KIT Graph Cache Layer v1

Caches query results for zero-lag IDE queries.
Invalidates on file hash change or Vantage rerun.
"""

import sqlite3
import hashlib
import json
import logging
import time
from typing import Dict, List, Optional, Any
from functools import lru_cache

logger = logging.getLogger("kit.graph.cache")

DEFAULT_TTL = 3600


class QueryCache:
    """LRU-style cache for graph queries."""

    def __init__(self, conn: sqlite3.Connection, ttl: int = DEFAULT_TTL):
        self.conn = conn
        self.ttl = ttl
        self._init_cache_table()

    def _init_cache_table(self):
        """Initialize cache table."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS query_cache (
                query_key TEXT PRIMARY KEY,
                query_type TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                ttl INTEGER NOT NULL,
                graph_hash TEXT
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_query_cache_type ON query_cache(query_type)
        """)

    def _make_key(self, query_type: str, **params) -> str:
        """Generate cache key."""
        param_str = json.dumps(params, sort_keys=True)
        return hashlib.sha256(f"{query_type}:{param_str}".encode()).hexdigest()

    def get(self, query_type: str, **params) -> Optional[Any]:
        """Get cached result if valid."""
        key = self._make_key(query_type, **params)
        row = self.conn.execute("""
            SELECT result_json, created_at, ttl, graph_hash
            FROM query_cache
            WHERE query_key = ?
        """, (key,)).fetchone()

        if not row:
            return None

        result_json, created_at, ttl, graph_hash = row

        if time.time() - created_at > ttl:
            self.invalidate(key)
            return None

        return json.loads(result_json)

    def set(self, query_type: str, graph_hash: str, result: Any, ttl: Optional[int] = None, **params):
        """Cache query result."""
        key = self._make_key(query_type, **params)
        ttl = ttl or self.ttl

        self.conn.execute("""
            INSERT OR REPLACE INTO query_cache
            (query_key, query_type, result_json, created_at, ttl, graph_hash)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (key, query_type, json.dumps(result), int(time.time()), ttl, graph_hash))

    def invalidate(self, key: str):
        """Invalidate single cache entry."""
        self.conn.execute("DELETE FROM query_cache WHERE query_key = ?", (key,))

    def invalidate_pattern(self, query_type: str):
        """Invalidate all entries of a query type."""
        self.conn.execute("DELETE FROM query_cache WHERE query_type = ?", (query_type,))

    def invalidate_all(self):
        """Clear entire cache."""
        self.conn.execute("DELETE FROM query_cache")
        logger.info("Query cache cleared")

    def invalidate_on_graph_change(self, new_hash: str):
        """Invalidate stale entries when graph changes."""
        stale = self.conn.execute("""
            SELECT query_key FROM query_cache
            WHERE graph_hash != ?
        """, (new_hash,)).fetchall()

        for row in stale:
            self.invalidate(row[0])

        logger.info(f"Invalidated {len(stale)} stale cache entries")

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        total = self.conn.execute("SELECT COUNT(*) FROM query_cache").fetchone()[0]

        by_type = dict(self.conn.execute("""
            SELECT query_type, COUNT(*)
            FROM query_cache
            GROUP BY query_type
        """).fetchall())

        return {
            "total_entries": total,
            "by_type": by_type
        }


def cached_blast(conn: sqlite3.Connection, graph_hash: str, symbol: str, max_depth: int = 5, **params) -> List:
    """Cached blast query."""
    cache = QueryCache(conn)

    result = cache.get("blast", symbol=symbol, max_depth=max_depth, **params)
    if result is not None:
        return result

    from kit.graph.api import GraphQueryAPI
    api = GraphQueryAPI(conn)
    result = api.blast(symbol, max_depth=max_depth, **params)

    cache.set("blast", graph_hash, result, symbol=symbol, max_depth=max_depth, **params)
    return result


def cached_impact(conn: sqlite3.Connection, graph_hash: str, symbol: str, **params) -> Dict:
    """Cached impact query."""
    cache = QueryCache(conn)

    result = cache.get("impact", symbol=symbol, **params)
    if result is not None:
        return result

    from kit.graph.api import GraphQueryAPI
    api = GraphQueryAPI(conn)
    result = api.impact(symbol, **params)

    cache.set("impact", graph_hash, result, symbol=symbol, **params)
    return result


def clear_all_caches(conn: sqlite3.Connection):
    """Clear all query caches."""
    cache = QueryCache(conn)
    cache.invalidate_all()