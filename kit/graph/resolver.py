"""
KIT Call Resolution Layer v1

Resolves raw call edges to canonical callees.
Implements: module resolution, class method resolution, alias tracking.
"""

import logging
import sqlite3
from collections import defaultdict
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("kit.graph.resolver")


class ResolutionMethod(Enum):
    MODULE = "module"
    CLASS = "class"
    ALIAS = "alias"
    INFERENCE = "inference"
    UNRESOLVED = "unresolved"


class ModuleFunctionResolver:
    """Resolves module.function() calls."""

    STDLIB = frozenset(
        {
            "os",
            "sys",
            "re",
            "json",
            "math",
            "time",
            "datetime",
            "collections",
            "itertools",
            "functools",
            "operator",
            "pathlib",
            "abc",
            "typing",
            "enum",
            "logging",
            "warnings",
            "copy",
            "pprint",
            "ast",
            "dis",
            "inspect",
        }
    )

    def __init__(self, project_prefix: str = "app"):
        self.project_prefix = project_prefix

    def resolve(self, call: str) -> tuple[str, float]:
        """Resolve module.function() pattern."""
        if "." not in call:
            return call, 0.3

        parts = call.split(".")
        if len(parts) < 2:
            return call, 0.3

        module = parts[0]
        if module in self.STDLIB:
            return f"python.{call}", 1.0

        if call.startswith("app.") or call.startswith("python."):
            return call, 0.9

        if module[0].islower():
            return f"{self.project_prefix}.{call}", 0.9

        return call, 0.5


class ClassContextResolver:
    """Resolves self.method() and class method calls."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._method_cache: dict[str, list[str]] = {}

    def load_class_hierarchy(self) -> dict[str, list[str]]:
        """Load class inheritance map from structure_edges."""
        inherits = self.conn.execute("""
            SELECT source_symbol, target_symbol
            FROM structure_edges
            WHERE edge_type = 'INHERITS'
        """)

        hierarchy: dict[str, list[str]] = defaultdict(list)
        for source, target in inherits:
            hierarchy[source].append(target)

        return dict(hierarchy)


class AliasTracker:
    """Tracks function aliases: fn = foo; fn()"""

    def __init__(self):
        self._alias_map: dict[str, str] = {}

    def add_alias(self, alias: str, original: str):
        """Record alias relationship."""
        self._alias_map[alias] = original

    def resolve(self, call: str) -> str | None:
        """Resolve alias chain to final target."""
        visited = set()
        current = call

        while current in self._alias_map and current not in visited:
            visited.add(current)
            current = self._alias_map[current]

        return current if current != call else None


class CallResolver:
    """Main call resolution pipeline."""

    def __init__(self, conn: sqlite3.Connection, project_prefix: str = "app"):
        self.conn = conn
        self.project_prefix = project_prefix

        self.module_resolver = ModuleFunctionResolver(project_prefix)
        self.class_resolver = ClassContextResolver(conn)
        self.alias_tracker = AliasTracker()

        self._resolution_cache: dict[str, tuple[str, str, float]] = {}

    def resolve_call_site(self, call_site: str, source_file: str | None = None) -> tuple[str, str, float]:
        """Resolve a single call site to canonical callee."""
        if call_site in self._resolution_cache:
            return self._resolution_cache[call_site]

        callee, method, confidence = self._resolve(call_site)

        self._resolution_cache[call_site] = (callee, method, confidence)
        return callee, method, confidence

    def _resolve(self, call_site: str) -> tuple[str, str, float]:
        """Internal resolution logic."""
        if "." not in call_site:
            return call_site, ResolutionMethod.UNRESOLVED.value, 0.3

        parts = call_site.split(".")

        if len(parts) >= 2:
            first_part = parts[0]
            if first_part[0].islower():
                resolved, conf = self.module_resolver.resolve(call_site)
                return resolved, ResolutionMethod.MODULE.value, conf

        if parts[-1] in ("save", "load", "get", "set", "create", "update", "delete", "fetch"):
            resolved, conf = self.module_resolver.resolve(call_site)
            return resolved, ResolutionMethod.INFERENCE.value, conf

        return call_site, ResolutionMethod.CLASS.value, 0.7

    def materialize_resolutions(self) -> int:
        """Materialize all resolutions to call_resolutions table."""
        raw_calls = self.conn.execute("""
            SELECT source_symbol, target_symbol, source_file, line
            FROM structure_edges
            WHERE edge_type = 'CALLS'
        """).fetchall()

        inserted = 0
        for caller, callee_raw, source_file, line in raw_calls:
            callee, method, confidence = self.resolve_call_site(callee_raw, source_file)

            try:
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO call_resolutions
                    (call_site, callee_canonical, source_file, line, confidence, resolution_method)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (caller, callee, source_file, line, confidence, method),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                continue

        self.conn.commit()
        logger.info(f"Materialized {inserted} call resolutions")
        return inserted


def resolve_all_calls(conn: sqlite3.Connection, project_prefix: str = "app") -> int:
    """Public API: resolve all CALLS edges in database."""
    resolver = CallResolver(conn, project_prefix)
    return resolver.materialize_resolutions()


def get_resolution_stats(conn: sqlite3.Connection) -> dict:
    """Get resolution statistics."""
    total = conn.execute("SELECT COUNT(*) FROM call_resolutions").fetchone()[0]

    by_method = dict(
        conn.execute("""
        SELECT resolution_method, COUNT(*) FROM call_resolutions GROUP BY resolution_method
    """).fetchall()
    )

    return {
        "total_resolutions": total,
        "by_method": by_method,
    }
