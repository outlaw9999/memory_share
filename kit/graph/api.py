"""
KIT Graph Query API v1

High-level API for graph reasoning: blast, impact, dependency_chain, influence_score.
"""

import sqlite3
import logging
from typing import Dict, List, Tuple, Optional
from enum import Enum

from kit.graph.query import get_blast_radius, TraversalDirection

logger = logging.getLogger("kit.graph.api")


class RelationType(Enum):
    DEPENDS_ON = "depends_on"
    EXTENDS = "extends"
    USES = "uses"
    DEFINES = "defines"
    REFERENCES = "references"


class GraphQueryAPI:
    """High-level graph reasoning API."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def blast(self, symbol: str, max_depth: int = 5, direction: str = "bidirectional") -> List[Dict]:
        """Get blast radius - all nodes within N hops."""
        dir_map = {
            "forward": TraversalDirection.FORWARD,
            "backward": TraversalDirection.BACKWARD,
            "bidirectional": TraversalDirection.BIDIRECTIONAL,
        }
        direction_enum = dir_map.get(direction.lower(), TraversalDirection.BIDIRECTIONAL)

        results = get_blast_radius(
            self.conn, symbol,
            max_depth=max_depth,
            direction=direction_enum
        )

        return [{"symbol": r[0], "distance": r[1], "edge_type": r[2]} for r in results]

    def impact(self, symbol: str, max_depth: int = 3) -> Dict:
        """Calculate impact - who depends on this symbol."""
        forward = get_blast_radius(
            self.conn, symbol,
            max_depth=max_depth,
            direction=TraversalDirection.FORWARD,
            edge_types=('IMPORTS', 'CALLS')
        )

        direct = [r for r in forward if r[1] == 1]
        transitive = [r for r in forward if r[1] > 1]

        return {
            "symbol": symbol,
            "direct_count": len(direct),
            "direct": [{"symbol": r[0], "edge_type": r[2]} for r in direct],
            "transitive_count": len(transitive),
            "transitive": [{"symbol": r[0], "distance": r[1], "edge_type": r[2]} for r in transitive],
            "total": len(forward)
        }

    def dependency_chain(self, from_symbol: str, to_symbol: str, max_length: int = 10) -> List[str]:
        """Find shortest dependency path from A to B."""
        result = self.conn.execute(f"""
            WITH RECURSIVE path_finder(source, target, distance, path) AS (
                SELECT source_symbol, target_symbol, 0, source_symbol || ' -> ' || target_symbol
                FROM structure_edges
                WHERE source_symbol = ? AND edge_type IN ('IMPORTS', 'INHERITS')
                UNION ALL
                SELECT se.source_symbol, se.target_symbol, pf.distance + 1, pf.path || ' -> ' || se.target_symbol
                FROM structure_edges se
                JOIN path_finder pf ON se.source_symbol = pf.target
                WHERE pf.distance < ? AND se.edge_type IN ('IMPORTS', 'INHERITS')
            )
            SELECT path FROM path_finder WHERE target = ? LIMIT 1
        """, (from_symbol, max_length, to_symbol)).fetchone()

        if not result:
            return []
        return result[0].split(' -> ')

    def influence_score(self, symbol: str, decay: float = 0.5) -> Dict:
        """Calculate weighted influence score."""
        results = get_blast_radius(
            self.conn, symbol,
            max_depth=10,
            direction=TraversalDirection.FORWARD,
            include_confidence=True
        )

        score = 0.0
        influence_map = {}

        for r in results:
            sym, dist, edge_type, conf = r
            weight = conf / (dist ** decay) if dist > 0 else conf
            influence_map[sym] = weight
            score += weight

        return {
            "symbol": symbol,
            "influence_score": round(score, 3),
            "nodes_affected": len(results),
            "top_influences": sorted(influence_map.items(), key=lambda x: x[1], reverse=True)[:10]
        }

    def execution_path(self, from_func: str, to_func: str) -> List[str]:
        """Find execution path from function A to function B."""
        result = self.conn.execute("""
            WITH RECURSIVE exec_path(source, target, distance, path) AS (
                SELECT call_site, callee_canonical, 0, call_site || ' -> ' || callee_canonical
                FROM call_resolutions
                WHERE call_site = ? AND resolution_method != 'unresolved'
                UNION ALL
                SELECT cr.call_site, cr.callee_canonical, ep.distance + 1, ep.path || ' -> ' || cr.callee_canonical
                FROM call_resolutions cr
                JOIN exec_path ep ON cr.call_site = ep.target
                WHERE ep.distance < 10 AND cr.resolution_method != 'unresolved'
            )
            SELECT path FROM exec_path WHERE target = ? LIMIT 1
        """, (from_func, to_func)).fetchone()

        if not result:
            return []
        return result[0].split(' -> ')

    def hot_paths(self, top_k: int = 10) -> List[Dict]:
        """Find most called functions."""
        results = self.conn.execute("""
            SELECT callee_canonical, COUNT(*) as cnt
            FROM call_resolutions
            WHERE resolution_method != 'unresolved'
            GROUP BY callee_canonical
            ORDER BY cnt DESC
            LIMIT ?
        """, (top_k,)).fetchall()

        return [{"function": r[0], "call_count": r[1]} for r in results]

    def runtime_impact(self, function: str) -> Dict:
        """Calculate runtime impact - who calls this function."""
        callers = self.conn.execute("""
            SELECT call_site, resolution_method
            FROM call_resolutions
            WHERE callee_canonical = ? AND resolution_method != 'unresolved'
        """, (function,)).fetchall()

        direct = [r[0] for r in callers]

        return {
            "function": function,
            "direct_callers": direct,
            "direct_count": len(direct),
            "total_runtime_impact": len(direct)
        }

    def simulate_failure(self, function: str) -> Dict:
        """Simulate cascade failure if function fails."""
        affected = self.conn.execute("""
            WITH RECURSIVE cascade(target, distance) AS (
                SELECT callee_canonical, 0
                FROM call_resolutions
                WHERE call_site = ?
                UNION ALL
                SELECT cr.callee_canonical, cascade.distance + 1
                FROM call_resolutions cr
                JOIN cascade ON cr.call_site = cascade.target
                WHERE cascade.distance < 5
            )
            SELECT DISTINCT target FROM cascade WHERE distance > 0
        """, (function,)).fetchall()

        affected_list = [r[0] for r in affected]
        criticality = min(len(affected_list) / 10.0, 1.0)

        return {
            "function": function,
            "affected_functions": affected_list[:20],
            "affected_count": len(affected_list),
            "criticality": round(criticality, 3)
        }


def quick_blast(db_path: str, symbol: str, max_depth: int = 5) -> List[Dict]:
    """Quick blast query from db path."""
    conn = sqlite3.connect(db_path)
    api = GraphQueryAPI(conn)
    results = api.blast(symbol, max_depth=max_depth)
    conn.close()
    return results


def quick_impact(db_path: str, symbol: str) -> Dict:
    """Quick impact query from db path."""
    conn = sqlite3.connect(db_path)
    api = GraphQueryAPI(conn)
    results = api.impact(symbol)
    conn.close()
    return results